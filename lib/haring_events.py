"""Turn a run's events.jsonl into the lines haring's readers show.

A run's event stream is the one record haring owns, and more than one command reads
it: haring-wait renders the whole stream live, and anything that wants a single
detail out of a run reads the same file. This module holds what they share — how one
tool call's arguments become a line of text, and how the stream becomes labelled
lines, thought tails, folded runs of one tool and retry counts.
"""
import json, time
from datetime import datetime

VALUE_LIMIT = 500  # most of one argument's value that is printed
ARGS_LIMIT = 1000  # most of one call's whole argument text that is printed
# Argument names never printed at all: each one holds a payload rather than context —
# the body of a file being written, and the two halves of an edit.
SKIP_ARGS = ("content", "old_string", "new_string")
# The argument printed first and bare: the first of these the call carries. It is the
# one that says what the call was, and the rest follow it as name=value.
MAIN_ARGS = ("command", "file_path", "pattern")

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

    Assistant and user events carry the UTC moment they happened; system events carry
    none and take the moment this reader saw them, which for a live tail is the same
    second. Stamping from the event rather than from the clock is what lets a reader
    that joined late replay a run with the real time each call was made.
    """
    if ts:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return time.time()


class RunReader:
    """Reads one run's events.jsonl and returns the lines added since the last read.

    Each line is a triple: the label that goes in the tool-name column — the tool's
    own name for a call, "thinking" or "says" for the worker's blocks, "api_retry"
    for a run of endpoint retries — the text that follows it, and the event's
    timestamp. A reader keeps reading the same path and gets only what it has not
    seen; it is the caller that prints, formats and clips.

    Four attributes a caller reads to know how the worker is doing:
      when     the last time a step or a retry was seen, on the caller's own clock,
               which is what "the worker has done nothing" is measured from
      when_ts  the same moment on the events' own clock, which is what the block
               tails are measured on; starts at the caller's `when_ts`, the moment
               the worker began, so an early block is judged against real time
      seen_at  the last time the stream produced anything at all, thinking included,
               which separates a worker that is generating from one that is silent
      last     whether the latest of those was a "step" or a "retry"
    """

    def __init__(self, when_ts=0.0):
        self.pos = 0        # where this reader stopped in the file last time
        self.seen = set()   # tool-call ids already reported
        # The fold state for a run of the same tool: its name, how many calls it has
        # folded, when the next fold line prints, and the distinct argument texts the
        # fold has held.
        self.tool = None
        self.n = 0
        self.next = 2
        self.args = set()
        self.retries = 0
        self.retry_next = 1
        self.when = time.time()
        self.when_ts = when_ts
        self.seen_at = 0.0
        self.last = None

    def read(self, path):
        """Every line the stream has added since the last read, oldest first."""
        out = []
        with open(path) as f:
            f.seek(self.pos)
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                self.seen_at = time.time()
                # The endpoint refusing the worker shows up here and nowhere else, so
                # it is announced like a step: it is the answer to "why has nothing
                # happened".
                if d.get("type") == "system" and d.get("subtype") == "api_retry":
                    self.retries += 1
                    self.last = "retry"
                    self.when = time.time()
                    self.when_ts = ts_value(d.get("timestamp"))
                    if self.retries >= self.retry_next:
                        out.append(("api_retry",
                                    f"x{self.retries} waiting on the endpoint",
                                    d.get("timestamp")))
                        self.retry_next = self.retries * 2
                    continue
                # A system event of subtype permission_denied carries a plain string
                # here, not an object, so every run where the deny list fires reaches
                # this line with a str. Anything without a content list has no tool
                # call in it either way.
                message = d.get("message")
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, list):
                    continue
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    # A thought or a line of speech prints in the layout a step uses,
                    # with its kind where the tool name sits, so the three are told
                    # apart at a glance. These feed only seen_at, not when: a worker
                    # can think for minutes without a step and is not stalled.
                    kind = b.get("type")
                    if kind in ("thinking", "text"):
                        ts = d.get("timestamp")
                        label = "thinking" if kind == "thinking" else "says"
                        rows = [l for l in (" ".join(x.split())
                                            for x in (b.get(kind) or "").splitlines())
                                if l]
                        # A single thought has filled 485 rows here and pushed every
                        # tool call out of the panel, and the ending of a thought is
                        # the part that says whether the route is wrong. The count
                        # line ahead of the kept rows keeps a reader from taking them
                        # for the whole thought. While the worker is acting,
                        # BLOCK_LINES_WORKING of them are enough of the ending and the
                        # steps keep the rest of the panel; once it has been quiet
                        # since its last step for as long as the waiting line needs,
                        # the thought is all there is to read and it keeps
                        # BLOCK_LINES. Measured on the events' own moments, not this
                        # reader's clock, so a replay sees the silences a live watch
                        # saw.
                        kept = (BLOCK_LINES if ts_value(ts) - self.when_ts >= IDLE_AFTER
                                else BLOCK_LINES_WORKING)
                        if len(rows) > kept:
                            out.append((label,
                                        f"{len(rows) - kept} earlier lines of this "
                                        f"block not shown", ts))
                            rows = rows[-kept:]
                        for l in rows:
                            out.append((label, l, ts))
                        continue
                    if kind != "tool_use":
                        continue
                    if b.get("id") in self.seen:
                        continue
                    self.seen.add(b.get("id"))
                    arg = render_args(b.get("input") or {})
                    name = b.get("name", "?")
                    ts = d.get("timestamp")
                    self.when = time.time()
                    self.when_ts = ts_value(ts)
                    self.last = "step"
                    # A run of one tool — a scan, a string of edits — would spend the
                    # whole display on near-identical rows. It gets one line at the
                    # second call and one at each doubling, and the line that does
                    # print carries the most recent argument. The same call repeating
                    # is a worker stuck in a loop and keeps this plain form; calls
                    # that differed say how many distinct ones the fold has held.
                    if name == self.tool:
                        self.n += 1
                        self.args.add(arg)
                        if self.n >= self.next:
                            if len(self.args) == 1:
                                out.append((name, f"x{self.n} {arg}", ts))
                            else:
                                out.append((name,
                                            f"x{self.n} {len(self.args)} different, "
                                            f"last: {arg}", ts))
                            self.next = self.n * 2
                    else:
                        self.tool, self.n, self.next, self.args = name, 1, 2, {arg}
                        out.append((name, arg, ts))
            self.pos = f.tell()
        return out
