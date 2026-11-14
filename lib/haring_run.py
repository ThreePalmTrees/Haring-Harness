"""The numbers a run's report holds, in the one place every reader gets them.

A run's report.json is the record of what it spent: turns, seconds and the token counts
under modelUsage. More than one command shows those numbers, and two commands that work
them out separately drift. `run_numbers` is the one function that reads them; haring-stats
prints what it returns and haring-stats-page embeds the same values, so a run cannot read
one way in a terminal and another in a browser.

The model is the run's own, named by its meta file. A report whose modelUsage names more
than one model still reports the worker's; a run whose meta names a model the report does
not carry falls back to the busiest entry. Reporting is not this module's job: a missing
or unreadable report raises, exactly as the reader that prints one line expects, and a
caller that must keep going catches it.
"""
import json, os


def read_meta(run):
    """A run's meta as a dict of the lines that carry `=`. A missing file is empty."""
    try:
        with open(os.path.join(run, "meta")) as f:
            return dict(l.strip().split("=", 1) for l in f if "=" in l)
    except OSError:
        return {}


def run_numbers(run, meta=None, report=None):
    """One run's numbers, as haring-stats prints them.

    report is the parsed report.json when the caller already has it; otherwise it is
    read from the run folder. Reading it is the caller's business when the file is
    missing, empty or not JSON: those raise, and a caller that shows many runs keeps
    that run as one with no report.
    """
    if report is None:
        with open(os.path.join(run, "report.json")) as f:
            report = json.load(f)
    if meta is None:
        meta = read_meta(run)
    mu = report.get("modelUsage") or {}
    model = meta.get("model") or ""
    if model not in mu:
        model = max(mu, key=lambda k: (mu[k] or {}).get("outputTokens") or 0, default="?")
    m = mu.get(model, {})
    ms = report.get("duration_ms", 0)
    return {
        "model": model,
        "in": m.get("inputTokens", 0),
        "out": m.get("outputTokens", 0),
        "cache_read": m.get("cacheReadInputTokens", 0),
        "turns": report.get("num_turns", 0),
        "secs": round(ms / 1000),
        "error": report.get("is_error"),
        "ended": report.get("terminal_reason") or report.get("stop_reason"),
        "denials": len(report.get("permission_denials") or []),
    }
