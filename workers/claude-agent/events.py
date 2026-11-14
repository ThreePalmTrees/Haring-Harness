"""The Claude Code subagent worker's transcript, as the haring core reads it.

A subagent the manager starts with Claude Code's Agent tool writes one transcript,
agent-<id>.jsonl: one JSON object per line, and the lines that carry anything are its
user turns and its assistant turns. The core keeps what every worker shares —
render_args, the step clock, retry counting and the report checks — and asks the run's
worker module three questions: session(), entries() and summary(). A run with no pid in
its meta asks a fourth, alive(), which this module answers from the sidecar meta file
Claude Code writes beside the transcript.
"""
import json, os
from datetime import datetime

# Claude Code prefixes a message the manager sent to a running subagent with this, and
# follows it with an instruction about the current task. A harness entry carries the
# manager's own words, so both the opening and that closing line are removed. A user
# turn holding anything else — a tool result, a system reminder — carries no entry.
COORDINATOR = "The coordinator sent a message while you were working:"
COORDINATOR_CLOSES = "Address this before completing your current task."


def epoch_ms(ts):
    """A transcript timestamp in epoch milliseconds, or None when it is not a moment.

    Claude Code stamps every line with an ISO 8601 UTC time. The report's first and last
    are the epoch milliseconds the other workers report, so the conversion lives here.
    """
    if isinstance(ts, (int, float)) and not isinstance(ts, bool):
        return int(ts)
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def session(event):
    """The session id this event names, or None."""
    return event.get("agentId") or None


def entries(event, seen):
    """What one line adds, as the core's entry dicts.

    seen holds the part ids already handed over, so a reader that comes back to the
    same tail reports each part once. The id is the line's own uuid and the block's
    place in it: Claude Code writes no part id, and one API response can arrive split
    over several lines. Tool names arrive as haring's readers already label them —
    Bash, Read, Grep — so there is no table to map.
    """
    kind = event.get("type")
    if kind not in ("user", "assistant"):
        return []
    ts = event.get("timestamp") if isinstance(event.get("timestamp"), str) else None
    message = event.get("message") if isinstance(event.get("message"), dict) else {}
    base = event.get("uuid") or message.get("id") or ts or "?"
    content = message.get("content")
    if kind == "user":
        if isinstance(content, str) and content.startswith(COORDINATOR):
            key = f"{base}:manager"
            if key in seen:
                return []
            seen.add(key)
            text = content[len(COORDINATOR):].lstrip("\n").rstrip()
            if text.endswith(COORDINATOR_CLOSES):
                text = text[:-len(COORDINATOR_CLOSES)].rstrip()
            return [{"kind": "manager", "text": text, "ts": ts}]
        return []
    if not isinstance(content, list):
        return []
    out = []
    for i, block in enumerate(content):
        if not isinstance(block, dict):
            continue
        key = f"{base}:{i}"
        if key in seen:
            continue
        seen.add(key)
        btype = block.get("type")
        if btype == "thinking":
            out.append({"kind": "thinking", "text": block.get("thinking") or "", "ts": ts})
        elif btype == "text":
            out.append({"kind": "says", "text": block.get("text") or "", "ts": ts})
        elif btype == "tool_use":
            args = block.get("input")
            out.append({"kind": "tool", "name": block.get("name") or "?",
                        "args": args if isinstance(args, dict) else {}, "ts": ts})
    return out


def summary(events):
    """What the transcript says about the run: the session it ended in, its report, and
    the numbers.

    One API response may be written over several lines with the same message id, each
    line repeating the response's usage, so the usage and the step are counted once per
    id. The report is the message of the last SubagentHandback call; a run that ended
    without one reports its last assistant text.
    """
    sid, reason, handback = None, None, None
    texts = {}       # message id -> its text blocks in order
    order = []       # message ids that carried text, oldest first
    counted = set()  # message ids whose usage is already in the totals
    steps = 0
    tokens = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
    first = last = None
    for d in events:
        if not isinstance(d, dict):
            continue
        ms = epoch_ms(d.get("timestamp"))
        if ms is not None:
            first = ms if first is None else min(first, ms)
            last = ms if last is None else max(last, ms)
        sid = d.get("agentId") or sid
        if d.get("type") != "assistant":
            continue
        message = d.get("message") if isinstance(d.get("message"), dict) else {}
        mid = message.get("id") or d.get("uuid")
        if mid not in counted:
            counted.add(mid)
            steps += 1
            usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
            details = (usage.get("output_tokens_details")
                       if isinstance(usage.get("output_tokens_details"), dict) else {})
            tokens["input"] += usage.get("input_tokens") or 0
            tokens["output"] += usage.get("output_tokens") or 0
            tokens["reasoning"] += details.get("thinking_tokens") or 0
            tokens["cache_read"] += usage.get("cache_read_input_tokens") or 0
            tokens["cache_write"] += usage.get("cache_creation_input_tokens") or 0
        reason = message.get("stop_reason") or reason
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                if mid not in texts:
                    texts[mid] = []
                    order.append(mid)
                texts[mid].append(block.get("text") or "")
            elif (block.get("type") == "tool_use"
                  and block.get("name") == "SubagentHandback"):
                inp = block.get("input")
                if isinstance(inp, dict) and "message" in inp:
                    value = inp.get("message")
                    handback = value if isinstance(value, str) else json.dumps(value)
    final = handback if handback is not None else (
        "".join(texts[order[-1]]) if order else "")
    return {"session": sid, "final": final, "error": None, "reason": reason,
            "steps": steps, "tokens": tokens, "cost": 0.0, "first": first, "last": last}


def alive(run, meta):
    """Whether the subagent is still working, answered from the file beside its transcript.

    Claude Code writes agent-<id>.meta.json beside agent-<id>.jsonl and adds
    "finished": true once the agent has ended. A run whose meta names no transcript, or
    whose sidecar file is missing or unreadable, has no evidence that the agent is going,
    so it reads as ended rather than as live.
    """
    transcript = str((meta or {}).get("transcript") or "").strip().strip("'")
    if not transcript:
        return False
    sidecar = os.path.splitext(transcript)[0] + ".meta.json"
    try:
        with open(sidecar) as f:
            state = json.load(f)
    except (OSError, ValueError):
        return False
    return isinstance(state, dict) and state.get("finished") is not True
