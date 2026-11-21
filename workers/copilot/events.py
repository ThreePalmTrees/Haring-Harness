"""The Copilot CLI worker's stream, as the haring core reads it.

A run's events.jsonl holds the JSON lines Copilot CLI writes with --output-format json,
followed by the one haring.usage line the worker's start program adds. The core keeps
what every worker shares — render_args, the step clock, retry counting and the report
checks — and asks the run's worker module three questions: session(), entries() and
summary().
"""
from datetime import datetime, timezone

# Copilot's tool names, under the labels every reader and the manager's skill already
# use. haring-report's evidence list counts Read, Glob, Grep and Bash by these labels,
# so a worker's shell call has to arrive as Bash to count as evidence at all.
TOOL_LABELS = {
    "view": "Read", "read": "Read",
    "rg": "Grep", "grep": "Grep",
    "glob": "Glob",
    "bash": "Bash",
    "edit": "Edit", "str_replace": "Edit", "str_replace_editor": "Edit",
    "multi_edit": "Edit",
    "create": "Write", "write": "Write",
    "apply_patch": "Patch",
}

# haring.usage carries the run's reasoning-token total once, and the core keeps part ids
# for the whole run, so this fixed id is what makes the count arrive once.
USAGE_PART = "haring.usage:reasoning"


def moment(value):
    """An event's ISO timestamp as a datetime in UTC, or None when it is not a moment."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value / 1000, timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(value):
    """An event's timestamp in the ISO 8601 UTC form ending in Z, or None."""
    parsed = moment(value)
    if parsed is None:
        return None
    return parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def epoch_ms(value):
    """An event's timestamp in epoch milliseconds, or None."""
    parsed = moment(value)
    if parsed is None:
        return None
    return round(parsed.timestamp() * 1000)


def session(event):
    """The session id this event names, or None."""
    kind = event.get("type")
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    if kind in ("session.start", "session.resume"):
        return data.get("sessionId") or None
    if kind == "result":
        return event.get("sessionId") or None
    return None


def entries(event, seen):
    """What one event adds, as the core's entry dicts.

    seen holds the part ids already handed over, so a reader that comes back to the same
    tail reports each part once. Copilot marks its deltas and model-call notices
    ephemeral, and those are not parts of the transcript. Reasoning is the one exception:
    Copilot marks it ephemeral too, but a non-empty block is still the worker's thinking.
    """
    if event.get("ephemeral") and event.get("type") != "assistant.reasoning":
        return []
    kind = event.get("type")
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    ts = iso(event.get("timestamp"))

    if kind == "tool.execution_start":
        key = data.get("toolCallId") or event.get("id")
        if not key or key in seen:
            return []
        seen.add(key)
        tool = data.get("toolName") or "?"
        args = data.get("arguments")
        return [{"kind": "tool", "name": TOOL_LABELS.get(tool, tool),
                 "args": args if isinstance(args, dict) else {}, "ts": ts}]

    if kind == "assistant.message":
        key = data.get("messageId") or event.get("id")
        text = data.get("content")
        if not key or key in seen or not isinstance(text, str) or not text:
            return []
        seen.add(key)
        return [{"kind": "says", "text": text, "ts": ts}]

    if kind == "assistant.reasoning":
        # This is the exception to the ephemeral guard above: a non-empty reasoning block
        # is text even though Copilot marks it ephemeral.
        key = data.get("reasoningId") or event.get("id")
        text = data.get("content")
        if not key or key in seen or not isinstance(text, str) or not text:
            return []
        seen.add(key)
        return [{"kind": "thinking", "text": text, "ts": ts}]

    if kind == "haring.usage":
        if USAGE_PART in seen:
            return []
        seen.add(USAGE_PART)
        return [{"kind": "thinking_tokens", "count": usage_tokens(data)["reasoning"]}]

    return []


def usage_tokens(data):
    """The run's token counts summed over every model in a haring.usage object."""
    tokens = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
    metrics = data.get("modelMetrics") if isinstance(data, dict) else None
    if not isinstance(metrics, dict):
        return tokens
    for model in metrics.values():
        usage = model.get("usage") if isinstance(model, dict) else None
        if not isinstance(usage, dict):
            continue
        tokens["input"] += usage.get("inputTokens") or 0
        tokens["output"] += usage.get("outputTokens") or 0
        tokens["reasoning"] += usage.get("reasoningTokens") or 0
        tokens["cache_read"] += usage.get("cacheReadTokens") or 0
        tokens["cache_write"] += usage.get("cacheWriteTokens") or 0
    return tokens


def summary(events):
    """What the stream says about the run: the session it ended in, the final message,
    the error if it ended on one, and the numbers."""
    sid = None
    final = ""
    error = None
    reason = None
    last_error = None
    steps = 0
    tokens = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
    usage = None
    stopped = False
    first = last = None
    for event in events:
        if not isinstance(event, dict):
            continue
        ms = epoch_ms(event.get("timestamp"))
        if ms is not None:
            first = ms if first is None else min(first, ms)
            last = ms if last is None else max(last, ms)
        named = session(event)
        if named is not None:
            sid = named
        kind = event.get("type")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        if kind == "assistant.message":
            text = data.get("content")
            if isinstance(text, str) and text:
                final = text
        elif kind == "assistant.turn_end":
            steps += 1
        elif kind == "session.error":
            message = data.get("message")
            if message is not None:
                error = message if isinstance(message, str) else str(message)
            error_type = data.get("errorType")
            last_error = error_type if isinstance(error_type, str) else None
        elif kind == "result":
            if event.get("exitCode") == 0:
                stopped = True
        elif kind == "haring.usage" and isinstance(data, dict):
            usage = data
    if usage is not None:
        tokens = usage_tokens(usage)
    if stopped:
        reason = "stop"
    else:
        reason = last_error
    return {"session": sid, "final": final, "error": error, "reason": reason,
            "steps": steps, "tokens": tokens, "cost": 0.0, "first": first, "last": last}
