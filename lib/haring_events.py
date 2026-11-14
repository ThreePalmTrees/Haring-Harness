"""Turn a run's events.jsonl into the entries haring's readers show.

A run's event stream is the one record haring owns, and more than one command reads
it: haring-wait renders the whole stream live, and anything that wants a single
detail out of a run reads the same file. This module holds what they share — how one
tool call's arguments become a line of text, the clock a step is timed by, and how the
stream becomes labelled entries: one per tool call, one per thinking or speech block
carrying the whole block, one per message the manager sent into a running worker, and the
reasoning tokens a step spent.

An event's shape belongs to the worker that wrote it, not here: the run's meta
worker= line names a module under workers/<name>/ that says which event names the
session, what one event adds, and what the stream sums to. No line means opencode,
the worker haring runs. The same directory holds that worker's programs — start,
steer, stop — so nothing in bin/ or here runs a harness command itself. That split
keeps these files the same whatever harness wrote the stream.

The throwing-away stays out of here: folding a run of one tool drops the calls it
counts, and keeping the tail of a thought drops the rest of the thought; both lose
evidence, and the only reader that wants them is the display with a row budget. So
haring-wait applies them after read() returns, and every other reader gets the stream
whole. BLOCK_LINES and BLOCK_LINES_WORKING stay here, because haring-wait needs both
numbers and this module is where the shared numbers live.

More than one command also asks whether a run's worker is still going, and the answer
takes the pid's command as well as the signal, so that test lives here too.
"""
import importlib.util, json, os, subprocess, time
from datetime import datetime

HARING_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
WORKERS = {}   # events module path -> the loaded module


def worker_dir(run):
    """The directory a run's worker lives in: workers/<name> under the haring root,
    where <name> is what the run's meta worker= line says or opencode when it says
    nothing. Its events.py says what an event means; start, steer and stop are the
    programs that run the harness and talk to it."""
    name = "opencode"
    try:
        with open(os.path.join(run, "meta")) as f:
            for line in f:
                if line.startswith("worker="):
                    name = line.strip().split("=", 1)[1].strip("'") or name
                    break
    except OSError:
        pass
    return os.path.join(HARING_ROOT, "workers", name)


def worker_events(run):
    """The events module of a run's worker, from its worker_dir. A file is imported once
    and kept, so a reader looking again at a run or another run of the same worker gets
    the module it already has. A missing file is named as it is, in place of a traceback
    that would not say which worker was asked for."""
    path = os.path.join(worker_dir(run), "events.py")
    name = os.path.basename(os.path.dirname(path))
    if path not in WORKERS:
        if not os.path.isfile(path):
            raise SystemExit(f"haring: no events module for worker '{name}': {path} is missing")
        spec = importlib.util.spec_from_file_location(f"haring_worker_{name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        WORKERS[path] = module
    return WORKERS[path]


def worker_conf(run):
    """The hints a run's worker declares for its harness, from workers/<name>/worker.conf
    beside the module worker_events loads.

    The file is written by hand when a worker is added, so every line is a hint and never
    a promise. thinking says the harness can show a thought in the stream, and fork says a
    continued run may fork its session. Each one is true only for the exact value yes; a
    missing file, a missing line or any other value is the safe default, False, so a wrong
    file cannot break a run.
    """
    hints = {"thinking": False, "fork": False}
    try:
        with open(os.path.join(worker_dir(run), "worker.conf")) as f:
            for line in f:
                key, sep, value = line.partition("=")
                key = key.strip()
                if sep and key in hints:
                    hints[key] = value.strip() == "yes"
    except OSError:
        pass
    return hints


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


def run_alive(run, meta=None):
    """Whether a run's worker is still going.

    A run whose meta carries a pid is tested by run_pid_alive, as every run haring starts
    as a process of its own is. A run with no pid — a Claude Code subagent the manager
    started with the Agent tool — has no process haring launched, so its worker module
    answers instead: alive(run, meta) when it defines one. A module with no such function
    cannot say a pid-less run is alive, and the run reads as ended.
    """
    if meta is None:
        try:
            with open(os.path.join(run, "meta")) as f:
                meta = dict(l.strip().split("=", 1) for l in f if "=" in l)
        except OSError:
            return False
    pid = str(meta.get("pid") or "").strip()
    if pid:
        return run_pid_alive(run, pid)
    test = getattr(worker_events(run), "alive", None)
    return bool(test and test(run, meta))


def live_session(run):
    """The session a run is working in: the first session id its events.jsonl names,
    else the id its start chose and wrote to the run's session file, else the one its
    meta names (old runs). A fresh run's session file is written before the worker does
    anything; a continued run's fork, when its worker forks, picks an id only the stream
    knows."""
    worker = worker_events(run)
    try:
        with open(os.path.join(run, "events.jsonl")) as f:
            for line in f:
                try:
                    sid = worker.session(json.loads(line))
                except ValueError:
                    continue
                if sid:
                    return sid
    except OSError:
        pass
    try:
        with open(os.path.join(run, "session")) as f:
            sid = f.read().strip()
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


VALUE_LIMIT = 500  # most of one argument's value that is printed
ARGS_LIMIT = 1000  # most of one call's whole argument text that is printed
# Argument names never printed at all: each one holds a payload rather than context —
# the body of a file being written, the two halves of an edit, and a patch's text.
SKIP_ARGS = ("content", "oldString", "newString", "patchText")
# The argument printed first and bare: the first of these the call carries. It is the
# one that says what the call was, and the rest follow it as name=value. OpenCode names
# the file `path` or `filePath`.
MAIN_ARGS = ("command", "filePath", "path", "pattern")

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


class RunReader:
    """Reads one run's events.jsonl and returns the entries added since the last read.

    Each entry is a triple: the label that goes in the tool-name column — the tool's
    own name for a call, "thinking", "says" or "manager" for the worker's blocks — the
    text that follows it, and the event's timestamp. A tool call is one entry with its
    arguments rendered. A thinking or speech block is one entry whose text is the whole
    block, its lines joined with newlines, so a caller that prints line by line splits
    it and one that wants the block whole has it. A reader keeps reading the same path
    and gets only what it has not seen; it is the caller that prints, formats, clips
    and trims.

    What one event means is its worker module's to say; this class owns the file
    position, the seen set, the clock and the retry count.

    Four attributes a caller reads to know how the worker is doing:
      when     the last time a step was seen, on the caller's own clock, which is what
               "the worker has done nothing" is measured from
      when_ts  the same moment on the events' own clock. It advances with every tool
               call and every retry line, in the order the entries come back, so a
               caller walking the list rebuilds it in step — which is how haring-wait
               judges a block's length against the silence before it
      seen_at  the last time the stream produced anything at all, thinking included,
               which separates a worker that is generating from one that is silent
      last     whether the latest progress was a "step" or a "retry"
      thinking_tokens  the reasoning tokens the stream has accumulated, summed from the
                       counts its worker's finished steps hand back, which carry the
                       count without producing an entry — the cost of a long thought
                       that no entry shows
      has_thought  whether the stream has carried a thought at all: a thinking entry,
                   or a thinking_tokens count above 0
    """

    def __init__(self, when_ts=0.0):
        self.pos = 0        # where this reader stopped in the file last time
        self.seen = set()   # tool-call ids already reported
        self.worker = None  # the run's worker module, loaded on the first read
        self.retries = 0    # haring-wait's api_retry line reads these two
        self.retry_next = 1
        self.thinking_tokens = 0
        self.has_thought = False
        self.when = time.time()
        self.when_ts = when_ts
        self.seen_at = 0.0
        self.last = None

    def read(self, path):
        """Every entry the stream has added since the last read, oldest first."""
        if self.worker is None:
            self.worker = worker_events(os.path.dirname(path))
        out = []
        with open(path) as f:
            f.seek(self.pos)
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                self.seen_at = time.time()
                for e in self.worker.entries(d, self.seen):
                    entry = self.entry(e)
                    if entry is not None:
                        out.append(entry)
            self.pos = f.tell()
        return out

    def entry(self, e):
        """One entry the worker module named, as the label, text and timestamp a reader
        prints; None when it carries no line and only feeds a counter."""
        kind = e.get("kind")
        ts = e.get("ts")
        if kind == "thinking_tokens":
            count = e.get("count") or 0
            self.thinking_tokens += count
            if count > 0:
                self.has_thought = True
            return None
        if kind == "tool":
            arg = render_args(e.get("args") or {})
            if "error" in e:
                arg = (arg + " — refused: "
                       + " ".join(str(e.get("error") or "").split()))[:ARGS_LIMIT]
            self.when = time.time()
            self.when_ts = ts_value(ts)
            self.last = "step"
            return (e.get("name", "?"), arg, ts)
        if kind in ("thinking", "says", "manager"):
            if kind == "thinking":
                self.has_thought = True
            rows = [l for l in (" ".join(x.split())
                                for x in (e.get("text") or "").splitlines()) if l]
            return (kind, "\n".join(rows), ts) if rows else None
        if kind == "retry":
            self.retries += 1
            self.last = "retry"
            self.when = time.time()
            self.when_ts = ts_value(ts)
            if self.retries >= self.retry_next:
                self.retry_next = self.retries * 2
                return ("api_retry", f"x{self.retries} waiting on the endpoint", ts)
        return None
