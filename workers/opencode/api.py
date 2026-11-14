"""One request to the OpenCode server, for the programs in this directory.

The server holds the session, so starting a turn against it, steering a live one and
stopping it all go through `opencode api`; this is the only place that command is built.
"""
import json, subprocess


def opencode_api(method, path, body=None):
    """One request as (ok, text). Text is the server's answer, or the error that kept the
    request from being made."""
    cmd = ["opencode", "api", method, path]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                             stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    text = (out.stdout + out.stderr).strip()
    return out.returncode == 0 and "HTTP 4" not in text and "HTTP 5" not in text, text
