"""The Copilot CLI subagent worker's transcript, as the haring core reads it.

A subagent the Copilot CLI manager starts with its own `task` tool writes its lines into
the manager's session log, ~/.copilot/session-state/<session>/events.jsonl, and every
line carries a top-level agentId. The run's events.jsonl holds only the lines for one
agent. The core keeps what every worker shares — render_args, the step clock, retry
counting and the report checks — and asks the run's worker module three questions:
session(), entries() and summary(). A run with no pid in its meta asks a fourth, alive(),
which this module answers from the manager's log and its own age.
"""
import importlib.util, json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.join(HERE, "..", "copilot", "events.py")

try:
    _spec = importlib.util.spec_from_file_location("haring_copilot_events", BASE_PATH)
    copilot = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(copilot)
except (AttributeError, FileNotFoundError, ImportError) as exc:
    raise ImportError(f"copilot-agent needs the command-line worker's events.py at {BASE_PATH}: {exc}")

# A Copilot session that dies mid-subagent writes no subagent.completed or
# subagent.failed. The manager's log is appended as the subagent works, and fifteen
# minutes without a write is far past any single step a subagent takes.
STALE_AFTER = 15 * 60  # seconds


def session(event):
    """The subagent id this event names, or None."""
    return event.get("agentId") or None


def entries(event, seen):
    """What one line adds, as the core's entry dicts.

    Tool calls, speech and thinking come from the command-line worker's module so both
    Copilot workers label the same stream the same way. A usage record adds the
    reasoning tokens it counted; the core keeps part ids for the whole run and that
    record's own id is what keeps each count to one.
    """
    out = copilot.entries(event, seen)
    if event.get("type") != "session.usage_record":
        return out
    key = event.get("id")
    if not key or key in seen:
        return out
    seen.add(key)
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    count = usage.get("reasoningTokens") or 0
    if not isinstance(count, (int, float)) or isinstance(count, bool):
        count = 0
    return out + [{"kind": "thinking_tokens", "count": int(count)}]


def summary(events):
    """What the subagent's lines say about the run: its report, its end and the numbers."""
    sid = None
    final = ""
    failed_error = None
    session_error = None
    error_type = None
    completed = False
    steps = 0
    tokens = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
    first = last = None
    for event in events:
        if not isinstance(event, dict):
            continue
        ms = copilot.epoch_ms(event.get("timestamp"))
        if ms is not None:
            first = ms if first is None else min(first, ms)
            last = ms if last is None else max(last, ms)
        sid = event.get("agentId") or sid
        kind = event.get("type")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        if kind == "assistant.message":
            text = data.get("content")
            if isinstance(text, str) and text:
                final = text
        elif kind == "assistant.turn_end":
            steps += 1
        elif kind == "subagent.completed":
            completed = True
        elif kind == "subagent.failed":
            message = data.get("error")
            if message is not None:
                failed_error = message if isinstance(message, str) else str(message)
        elif kind == "session.error":
            message = data.get("message")
            if message is not None:
                session_error = message if isinstance(message, str) else str(message)
            kind_error = data.get("errorType")
            if isinstance(kind_error, str):
                error_type = kind_error
        elif kind == "session.usage_record":
            usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
            tokens["input"] += usage.get("inputTokens") or 0
            tokens["output"] += usage.get("outputTokens") or 0
            tokens["reasoning"] += usage.get("reasoningTokens") or 0
            tokens["cache_read"] += usage.get("cacheReadTokens") or 0
            tokens["cache_write"] += usage.get("cacheWriteTokens") or 0
    error = failed_error if failed_error is not None else session_error
    reason = "stop" if completed else error_type
    return {"session": sid, "final": final, "error": error, "reason": reason,
            "steps": steps, "tokens": tokens, "cost": 0.0, "first": first, "last": last}


def alive(run, meta):
    """Whether the subagent is still working, answered from the manager's session log.

    A run whose meta names no transcript or no agent id has no evidence that the
    subagent is going, so it reads as ended. A log that has not been written for
    STALE_AFTER is ended too, because a session that dies mid-subagent writes no
    subagent.completed or subagent.failed. A completed or failed line for this agent id
    is the end, whoever started reading it.
    """
    meta = meta or {}
    transcript = str(meta.get("transcript") or "").strip().strip("'")
    agent_id = str(meta.get("agent_id") or "").strip().strip("'")
    if not transcript or not agent_id:
        return False
    try:
        if time.time() - os.path.getmtime(transcript) >= STALE_AFTER:
            return False
    except OSError:
        return False
    try:
        with open(transcript, errors="ignore") as f:
            for line in f:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(event, dict) or event.get("agentId") != agent_id:
                    continue
                if event.get("type") in ("subagent.completed", "subagent.failed"):
                    return False
    except OSError:
        return False
    return True
