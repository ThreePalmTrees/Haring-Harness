"""Turn an OpenCode run's events.jsonl into the report.json haring's readers already read.

    python3 haring_report.py <run-folder> [schema-file|-] [--final] [--no-answer]

OpenCode has no flag that holds a run to a schema, so the worker is told the schema in
its first message, and its final message is the report. This reads that message back,
parses it as JSON and checks it against the schema. The report.json it writes has the
shape haring-report, haring-wait, haring-stats and haring-kill read: structured_output,
result, session_id, is_error, num_turns, duration_ms, modelUsage.

A schema of `-`, or no schema at all, is the no-schema mode: the final text is a
success with no structured_output. haring-pulse uses it for an adopted agent-kind run,
which has no report shape to match.

Exits 0 with report.json written when the report parsed and matched. Exits 1 with the
problem on standard output, and nothing written, when it did not and --final is not
given — the launcher sends the problem back to the same session and asks again. With
--final a report that never matched is written anyway, without structured_output and
with is_error set, so the manager reads the raw text rather than nothing. Exits 2,
writing nothing, when the stream holds no answer at all — a run that never started, or
one stopped before it said anything — which leaves report.json empty, the signal
haring-wait and haring-kill already read as "no report". --no-answer writes that report
instead, with is_error set and an empty result, so a caller that must not retry gets one.
The no-schema mode writes the same no-answer report rather than exiting 2.
"""
import json, os, sys
import haring_events

TYPES = {
    "string": str, "boolean": bool, "object": dict, "array": list,
    "integer": int, "number": (int, float), "null": type(None),
}


def problems(value, schema, where="report"):
    """Every way value fails schema, as sentences. Covers what haring's schemas use:
    type, enum, required, properties, additionalProperties false, and items."""
    out = []
    kinds = schema.get("type")
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        ok = any(isinstance(value, TYPES[k]) and not (k in ("integer", "number")
                                                      and isinstance(value, bool))
                 for k in kinds if k in TYPES)
        if not ok:
            return [f"{where} must be {' or '.join(kinds)}, not {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{where} must be one of {schema['enum']}, not {value!r}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                out.append(f"{where} is missing the required field '{name}'")
        if schema.get("additionalProperties") is False:
            for name in value:
                if name not in props:
                    out.append(f"{where} has a field the schema does not list: '{name}'")
        for name, sub in props.items():
            if name in value:
                out.extend(problems(value[name], sub, f"{where}.{name}"))
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for i, item in enumerate(value):
            out.extend(problems(item, schema["items"], f"{where}[{i}]"))
    return out


def parse(text):
    """The JSON object a final message holds, or None. A clean object is the contract;
    a fenced one or one with words around it is taken too, since the fields are what
    the manager needs and refusing them over a fence costs a whole extra turn."""
    text = text.strip()
    candidates = [text]
    if text.startswith("```"):
        body = text.split("\n", 1)[1] if "\n" in text else ""
        candidates.append(body.rsplit("```", 1)[0])
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start:end + 1])
    for c in candidates:
        try:
            value = json.loads(c)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def read_events(path):
    rows = []
    try:
        with open(path) as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return rows


def build_report(run, s, meta, found, trouble):
    """The report.json body a run's stream and meta add up to.

    found and trouble are the schema's answer: a matching object, or the problems the
    final message has. A run with no structured output — the raw form of a known kind
    that did not match, and an agent-kind report that has no schema — carries neither
    structured_output nor a claim that one is missing.
    """
    model = meta.get("model", "?")
    started = haring_events.run_started(run, meta) * 1000
    t = s["tokens"]
    usage = {"inputTokens": t["input"], "outputTokens": t["output"],
             "cacheReadInputTokens": t["cache_read"], "cacheCreationInputTokens": t["cache_write"],
             "reasoningTokens": t["reasoning"], "costUSD": round(s["cost"], 6)}
    report = {
        "type": "result",
        "subtype": "error" if trouble else "success",
        "is_error": bool(trouble),
        "session_id": s["session"],
        "result": s["final"] or s["error"] or "",
        "num_turns": s["steps"],
        "duration_ms": max(0, int((s["last"] or started) - started)),
        "stop_reason": s["reason"],
        "modelUsage": {model: usage},
        "usage": {"input_tokens": t["input"], "output_tokens": t["output"],
                  "cache_read_input_tokens": t["cache_read"]},
    }
    if trouble:
        report["report_problems"] = trouble
    elif found is not None:
        report["structured_output"] = found
    return report


def write_report(run, report):
    """Replace the run's report.json with this body in one move."""
    tmp = os.path.join(run, "report.json.tmp")
    with open(tmp, "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    os.replace(tmp, os.path.join(run, "report.json"))


def main():
    args = [a for a in sys.argv[1:] if a not in ("--final", "--no-answer")]
    final = "--final" in sys.argv[1:]
    no_answer = "--no-answer" in sys.argv[1:]
    if len(args) not in (1, 2):
        print("usage: haring_report.py <run-folder> [schema-file|-] [--final] [--no-answer]",
              file=sys.stderr)
        sys.exit(2)
    run = args[0]
    schema_path = args[1] if len(args) == 2 else "-"
    raw = schema_path == "-"
    schema = None
    if not raw and not no_answer:
        with open(schema_path) as f:
            schema = json.load(f)
    rows = read_events(os.path.join(run, "events.jsonl"))
    s = haring_events.worker_events(run).summary(rows)
    meta = {}
    try:
        meta = dict(l.strip().split("=", 1) for l in open(os.path.join(run, "meta")) if "=" in l)
    except OSError:
        pass
    if no_answer:
        empty = dict(s)
        empty["final"] = ""
        empty["error"] = None
        write_report(run, build_report(run, empty, meta, None,
                                       ["the run ended with no answer"]))
        sys.exit(0)
    # A run with no schema — a Claude Code subagent of an unknown kind — has no report
    # shape to match, so its raw final text is a success. A run that said nothing at all
    # gets one error report with an empty result, which ends the caller's retries.
    if raw:
        trouble = [] if (s["final"] or s["error"]) else ["the run ended with no answer"]
        write_report(run, build_report(run, s, meta, None, trouble))
        sys.exit(0)
    if not s["final"] and not s["error"]:
        sys.exit(2)

    found = parse(s["final"]) if s["final"] else None
    if found is None:
        trouble = (["the final message is not a JSON object"] if s["final"]
                   else [f"the run ended on an error before any answer: {s['error']}"])
    else:
        trouble = problems(found, schema)
    if trouble and not final:
        print("\n".join(trouble))
        sys.exit(1)

    write_report(run, build_report(run, s, meta, found, trouble))
    sys.exit(0)


if __name__ == "__main__":
    main()
