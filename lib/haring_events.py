"""Turn a run's events.jsonl into the entries haring's readers show.

A run's event stream is the one record haring owns, and more than one command reads
it: haring-wait renders the whole stream live, and anything that wants a single
detail out of a run reads the same file. This module holds what they share — how one
tool call's arguments become a line of text, and how the stream becomes labelled
entries: one per tool call, one per thinking or speech block carrying the whole
block, and counted endpoint retries.

The counting stays here and the throwing-away does not, because the two are not the
same kind of compression. Every retry is the same event, so one line saying how many
there were carries the whole fact. Folding a run of one tool drops the calls it
counts, and keeping the tail of a thought drops the rest of the thought; those lose
evidence, and the only reader that wants them is the display with a row budget. So
haring-wait applies both after read() returns, and every other reader gets the stream
whole. BLOCK_LINES and BLOCK_LINES_WORKING stay here, because haring-wait needs both
numbers and this module is where the shared numbers live.
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
# Tools whose arguments are never printed: the call itself is the news, and its
# arguments are the report the worker is handing over, which haring-report prints in
# full a moment later. Rendering them here spends a thousand characters of every
# reader's display saying again what the next command says better.
SKIP_TOOLS = ("StructuredOutput",)

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
    """Reads one run's events.jsonl and returns the entries added since the last read.

    Each entry is a triple: the label that goes in the tool-name column — the tool's
    own name for a call, "thinking" or "says" for the worker's blocks, "api_retry"
    for a run of endpoint retries — the text that follows it, and the event's
    timestamp. A tool call is one entry with its arguments rendered. A thinking or
    speech block is one entry whose text is the whole block, its lines joined with
    newlines, so a caller that prints line by line splits it and one that wants the
    block whole has it. A reader keeps reading the same path and gets only what it
    has not seen; it is the caller that prints, formats, clips and trims.

    Four attributes a caller reads to know how the worker is doing:
      when     the last time a step or a retry was seen, on the caller's own clock,
               which is what "the worker has done nothing" is measured from
      when_ts  the same moment on the events' own clock. It advances with every tool
               call and every retry, in the order the entries come back, so a caller
               walking the list rebuilds it in step — which is how haring-wait
               judges a block's length against the silence before it
      seen_at  the last time the stream produced anything at all, thinking included,
               which separates a worker that is generating from one that is silent
      last     whether the latest of those was a "step" or a "retry"
    """

    def __init__(self, when_ts=0.0):
        self.pos = 0        # where this reader stopped in the file last time
        self.seen = set()   # tool-call ids already reported
        self.retries = 0
        self.retry_next = 1
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
                # The endpoint refusing the worker shows up here and nowhere else, so
                # it is announced like a step: it is the answer to "why has nothing
                # happened". Counting is the one compression kept here, because every
                # retry is the same event and the count carries the whole fact.
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
                    # A thought or a line of speech arrives as one entry in the layout
                    # a step uses, with its kind where the tool name sits, so the three
                    # are told apart at a glance. These feed only seen_at, not when: a
                    # worker can think for minutes without a step and is not stalled.
                    kind = b.get("type")
                    if kind in ("thinking", "text"):
                        label = "thinking" if kind == "thinking" else "says"
                        # The block goes out whole: its lines with the blank ones gone
                        # and runs of whitespace collapsed, joined with newlines. The
                        # caller splits it to print line by line, and the display that
                        # keeps only a tail trims it there, where the row budget lives.
                        rows = [l for l in (" ".join(x.split())
                                            for x in (b.get(kind) or "").splitlines())
                                if l]
                        out.append((label, "\n".join(rows), d.get("timestamp")))
                        continue
                    if kind != "tool_use":
                        continue
                    if b.get("id") in self.seen:
                        continue
                    self.seen.add(b.get("id"))
                    name = b.get("name", "?")
                    arg = "" if name in SKIP_TOOLS else render_args(b.get("input") or {})
                    ts = d.get("timestamp")
                    self.when = time.time()
                    self.when_ts = ts_value(ts)
                    self.last = "step"
                    # One entry per call: a run of one tool is the caller's to fold,
                    # since the fold throws calls away and only a display with a row
                    # budget wants that.
                    out.append((name, arg, ts))
            self.pos = f.tell()
        return out
