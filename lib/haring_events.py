"""Turn a run's events.jsonl into the entries haring's readers show.

A run's event stream is the one record haring owns, and more than one command reads
it: haring-wait renders the whole stream live, and anything that wants a single
detail out of a run reads the same file. This module holds what they share — how one
tool call's arguments become a line of text, and how the stream becomes labelled
entries: one per tool call, one per thinking or speech block carrying the whole
block, and the reasoning tokens a step spent.

The throwing-away stays out of here: folding a run of one tool drops the calls it
counts, and keeping the tail of a thought drops the rest of the thought; both lose
evidence, and the only reader that wants them is the display with a row budget. So
haring-wait applies them after read() returns, and every other reader gets the stream
whole. BLOCK_LINES and BLOCK_LINES_WORKING stay here, because haring-wait needs both
numbers and this module is where the shared numbers live.

More than one command also asks whether a run's worker is still going, and the answer
takes the pid's command as well as the signal, so that test lives here too.
"""
import json, os, subprocess, time
from datetime import datetime


def run_pid_alive(run, pid):
    """Whether a run's worker is still going: its pid answering signal 0, and the
    command that pid carries naming the run's folder.

    A pid alone is not the worker. A freed pid is handed to whatever starts next, so a
    dead run whose pid now belongs to an unrelated process reads as live and a worker
    refuses to start beside it; the runner shell is started as /bin/sh <run>/run.sh, so
    its command always contains the run folder's basename, and a command without that
    basename is some other process. The basename is matched rather than the whole path
    because a process carries the path it was handed and realpath resolves symlinks —
    on macOS /tmp is a link to /private/tmp, so the realpath of a run under /tmp matches
    no command line.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        out = subprocess.run(["ps", "-p", str(pid), "-o", "command="],
                             capture_output=True, text=True)
    except OSError:
        return False
    return out.returncode == 0 and os.path.basename(run.rstrip("/")) in out.stdout


def live_session(run):
    """The OpenCode session a run is working in: the first session id its events.jsonl
    names, else the one its meta names. A fresh run's meta already holds it; a continued
    run forks under an id OpenCode picks, which only the stream knows."""
    try:
        with open(os.path.join(run, "events.jsonl")) as f:
            for line in f:
                try:
                    sid = json.loads(line).get("sessionID")
                except ValueError:
                    continue
                if sid:
                    return sid
    except OSError:
        pass
    try:
        with open(os.path.join(run, "meta")) as f:
            for line in f:
                if line.startswith("session_id="):
                    return line.strip().split("=", 1)[1].strip("'")
    except OSError:
        pass
    return ""


def opencode_api(method, path, body=None):
    """One request to the OpenCode server through `opencode api`, as (ok, text). The
    server holds the session, so stopping or steering a worker goes through it."""
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

VALUE_LIMIT = 500  # most of one argument's value that is printed
ARGS_LIMIT = 1000  # most of one call's whole argument text that is printed
# Argument names never printed at all: each one holds a payload rather than context —
# the body of a file being written, the two halves of an edit, and a patch's text.
SKIP_ARGS = ("content", "oldString", "newString", "patchText")
# The argument printed first and bare: the first of these the call carries. It is the
# one that says what the call was, and the rest follow it as name=value. OpenCode names
# the file `path` or `filePath`.
MAIN_ARGS = ("command", "filePath", "path", "pattern")
# OpenCode's tool names, under the labels every reader and the manager's skill already
# use. haring-report's evidence list counts Read, Glob, Grep and Bash by these labels,
# so a worker's shell call has to arrive as Bash to count as evidence at all.
TOOL_LABELS = {"read": "Read", "glob": "Glob", "grep": "Grep", "shell": "Bash",
               "edit": "Edit", "write": "Write", "patch": "Patch",
               "todowrite": "TodoWrite"}

BLOCK_LINES = 10  # how much of a finished thought is worth reading
BLOCK_LINES_WORKING = 3  # while the worker acts, the steps need the rest of the panel
IDLE_AFTER = 60   # seconds without a printed step before a reader speaks up


def render_args(args):
    """One tool call's arguments as a single line of text.

    The main argument comes first and bare, because it is what the call was — the
    command run, the file touched, the pattern sought. A Read that names only its
    file reads the same as one naming a line range, and a Grep that names only its
    pattern reads the same as one naming the file it searched, so every remaining
    argument follows as name=value, sorted by name. Names in SKIP_ARGS never print:
    they hold payloads, not context. One call's whole text is cut at ARGS_LIMIT so
    no argument, however large, spends more than its share of the display.
    """
    main = next((name for name in MAIN_ARGS if name in args), None)
    pieces = []
    if main is not None:
        value = args[main]
        pieces.append(" ".join(str(value).split())[:VALUE_LIMIT])
    for name in sorted(args):
        if name == main or name in SKIP_ARGS:
            continue
        value = args[name]
        pieces.append(f"{name}=" + " ".join(str(value).split())[:VALUE_LIMIT])
    return " ".join(pieces)[:ARGS_LIMIT]


def ts_value(ts):
    """The moment an event happened, as a number this reader can subtract from another.

    A stream's moment arrives as epoch milliseconds, or as an ISO 8601 string that
    already holds UTC; either becomes epoch seconds. A missing or unreadable moment
    takes the moment this reader saw it, which for a live tail is the same second.
    Stamping from the event rather than from the clock is what lets a reader that
    joined late replay a run with the real time each call was made.
    """
    if isinstance(ts, (int, float)) and not isinstance(ts, bool):
        return ts / 1000
    if ts:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return time.time()


def iso(ms):
    """An OpenCode event's epoch milliseconds in the ISO 8601 form every reader and
    said.jsonl already order by."""
    secs, frac = divmod(ms / 1000, 1)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(secs)) + ".%03dZ" % (frac * 1000)


class RunReader:
    """Reads one run's events.jsonl and returns the entries added since the last read.

    Each entry is a triple: the label that goes in the tool-name column — the tool's
    own name for a call, "thinking" or "says" for the worker's blocks — the text that
    follows it, and the event's timestamp. A tool call is one entry with its arguments
    rendered. A thinking or speech block is one entry whose text is the whole block,
    its lines joined with newlines, so a caller that prints line by line splits it and
    one that wants the block whole has it. A reader keeps reading the same path and
    gets only what it has not seen; it is the caller that prints, formats, clips and
    trims.

    Four attributes a caller reads to know how the worker is doing:
      when     the last time a step was seen, on the caller's own clock, which is what
               "the worker has done nothing" is measured from
      when_ts  the same moment on the events' own clock. It advances with every tool
               call, in the order the entries come back, so a caller walking the list
               rebuilds it in step — which is how haring-wait judges a block's length
               against the silence before it
      seen_at  the last time the stream produced anything at all, thinking included,
               which separates a worker that is generating from one that is silent
      last     "step" once a tool call has been seen
      thinking_tokens  the reasoning tokens the stream has accumulated, summed from the
                       steps that finished, which carry the count without producing an
                       entry — the cost of a long thought that no entry shows
    """

    def __init__(self, when_ts=0.0):
        self.pos = 0        # where this reader stopped in the file last time
        self.seen = set()   # tool-call ids already reported
        self.retries = 0    # haring-wait's api_retry line reads these two
        self.retry_next = 1
        self.thinking_tokens = 0
        self.when = time.time()
        self.when_ts = when_ts
        self.seen_at = 0.0
        self.last = None

    def read(self, path):
        """Every entry the stream has added since the last read, oldest first."""
        out = []
        with open(path) as f:
            f.seek(self.pos)
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                self.seen_at = time.time()
                # An OpenCode worker's stream: one event per finished part, the part
                # under "part" and the moment in epoch milliseconds. Any other line —
                # a run's error event, say — carries no entry.
                if isinstance(d.get("part"), dict) and d.get("type") in (
                        "tool_use", "text", "reasoning", "step_start", "step_finish"):
                    out.extend(self.opencode(d))
            self.pos = f.tell()
        return out

    def opencode(self, d):
        """The entries one OpenCode event adds: a tool call is a step, a thought or a
        line of speech feeds seen_at only."""
        part = d["part"]
        ms = d.get("timestamp")
        ts = iso(ms) if isinstance(ms, (int, float)) else None
        kind = d["type"]
        if kind == "step_finish":
            # The reasoning a step spent arrives with the step's end, not as its own
            # event, so this is where the run's thinking count grows.
            key = part.get("id")
            if key not in self.seen:
                self.seen.add(key)
                self.thinking_tokens += (part.get("tokens") or {}).get("reasoning") or 0
            return []
        if kind in ("text", "reasoning"):
            key = part.get("id")
            if key in self.seen:
                return []
            self.seen.add(key)
            rows = [l for l in (" ".join(x.split())
                                for x in (part.get("text") or "").splitlines()) if l]
            return [("thinking" if kind == "reasoning" else "says", "\n".join(rows), ts)] if rows else []
        if kind != "tool_use":
            return []
        key = part.get("id") or part.get("partID")
        if key in self.seen:
            return []
        self.seen.add(key)
        tool = part.get("tool", "?")
        name = TOOL_LABELS.get(tool, tool)
        state = part.get("state") or {}
        arg = render_args(state.get("input") or {})
        if state.get("status") == "error":
            arg = (arg + " — refused: " + " ".join(str(state.get("error") or "").split()))[:ARGS_LIMIT]
        self.when = time.time()
        self.when_ts = ts_value(ts)
        self.last = "step"
        return [(name, arg, ts)]
