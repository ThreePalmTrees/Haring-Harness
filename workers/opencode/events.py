"""The OpenCode worker's event stream, as the haring core reads it.

A run's events.jsonl holds one JSON object per line, and this module is the one place
that knows what those objects mean: which field names the run's session, which carry a
step's parts, and what a whole stream adds up to. The core keeps what every worker
shares — render_args, the step clock, retry counting and the report checks — and asks
the run's worker module three questions: session(), entries() and summary().
"""
import json, time

# OpenCode's tool names, under the labels every reader and the manager's skill already
# use. haring-report's evidence list counts Read, Glob, Grep and Bash by these labels,
# so a worker's shell call has to arrive as Bash to count as evidence at all.
TOOL_LABELS = {"read": "Read", "glob": "Glob", "grep": "Grep", "shell": "Bash",
               "edit": "Edit", "write": "Write", "patch": "Patch",
               "todowrite": "TodoWrite"}


def iso(ms):
    """An event's epoch milliseconds in the ISO 8601 form every reader and said.jsonl
    already order by."""
    secs, frac = divmod(ms / 1000, 1)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(secs)) + ".%03dZ" % (frac * 1000)


def session(event):
    """The session id this event names, or None."""
    return event.get("sessionID") or None


def entries(event, seen):
    """What one event adds, as the core's entry dicts.

    seen holds the part ids already handed over, so a reader that comes back to the
    same tail reports each part once. A step's reasoning tokens arrive with the step's
    end and come out as a count, since they carry no text of their own.
    """
    ms = event.get("timestamp")
    ts = iso(ms) if isinstance(ms, (int, float)) else None
    kind = event.get("type")
    if kind == "retry":
        return [{"kind": "retry", "ts": ts}]
    part = event.get("part")
    if not isinstance(part, dict):
        return []
    if kind == "step_finish":
        key = part.get("id")
        if key in seen:
            return []
        seen.add(key)
        return [{"kind": "thinking_tokens",
                 "count": (part.get("tokens") or {}).get("reasoning") or 0}]
    if kind in ("text", "reasoning"):
        key = part.get("id")
        if key in seen:
            return []
        seen.add(key)
        return [{"kind": "thinking" if kind == "reasoning" else "says",
                 "text": part.get("text") or "", "ts": ts}]
    if kind != "tool_use":
        return []
    key = part.get("id") or part.get("partID")
    if key in seen:
        return []
    seen.add(key)
    tool = part.get("tool", "?")
    state = part.get("state") or {}
    e = {"kind": "tool", "name": TOOL_LABELS.get(tool, tool),
         "args": state.get("input") or {}, "ts": ts}
    if state.get("status") == "error":
        e["error"] = state.get("error") or ""
    return [e]


def summary(events):
    """What the stream says about the run: the session it ended in, the final message,
    the error if it ended on one, and the numbers."""
    sid, error, reason = None, None, None
    texts = {}       # messageID -> its text parts in order
    order = []       # messageIDs that carried text, oldest first
    steps = 0
    tokens = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
    cost = 0.0
    first = last = None
    for d in events:
        ts = d.get("timestamp")
        if isinstance(ts, (int, float)):
            first = ts if first is None else first
            last = ts
        sid = d.get("sessionID") or sid
        part = d.get("part") or {}
        kind = d.get("type")
        if kind == "text":
            mid = part.get("messageID")
            if mid not in texts:
                texts[mid] = []
                order.append(mid)
            texts[mid].append(part.get("text") or "")
        elif kind == "step_finish":
            steps += 1
            reason = part.get("reason") or reason
            t = part.get("tokens") or {}
            cache = t.get("cache") or {}
            tokens["input"] += t.get("input") or 0
            tokens["output"] += t.get("output") or 0
            tokens["reasoning"] += t.get("reasoning") or 0
            tokens["cache_read"] += cache.get("read") or 0
            tokens["cache_write"] += cache.get("write") or 0
            cost += part.get("cost") or 0
        elif kind == "error":
            err = d.get("error")
            error = (err.get("message") if isinstance(err, dict) else err) or d.get("message") \
                or json.dumps(d)[:500]
    final = "".join(texts[order[-1]]) if order else ""
    return {"session": sid, "final": final, "error": error, "reason": reason,
            "steps": steps, "tokens": tokens, "cost": cost, "first": first, "last": last}
