# Worker contract

haring has two parts.

The core is `bin/` and `lib/`. It starts runs, reads their event streams, builds
reports, watches live runs, steers them and stops them.

A worker is everything under `workers/<name>/`. It knows one coding-agent harness:
how to start it, how to send a message to it, how to stop it, and what its event
stream means.

The core calls the worker folder by path. It does not import the harness and does not
read the harness's own configuration. This file describes what a worker folder must
provide and what the core does with it today. `workers/opencode/` is the worked
example for every part.

## 1. What a worker folder is

A worker folder lives at `workers/<name>/` under the haring root. The name is the
value of the `worker=` line in a run's `meta` file, or `opencode` when the run names
none.

The core uses these files.

- `worker.conf` holds the model list and two hints. A fresh launch cannot run without
  a readable model list.
- `events.py` is a Python module with three functions. Every command that reads a
  run's event stream loads it.
- `start` runs one worker turn and writes the event stream.
- `steer` delivers a message into a live session.
- `stop` interrupts a live session.
- `agents-config` installs, removes and checks the worker's harness-side files.
- `agents/<kind>.md` is one file per kind. Only the worker's own `agents-config`
  reads these. The core never reads them.
- `api.py` is a helper module used by the OpenCode `steer` and `stop`. The core never
  reads it.

A worker folder may hold other files. The core ignores them.

`start`, `steer`, `stop` and `agents-config` must be executable. `events.py` and
`worker.conf` must be readable. `worker.conf` must be a file, not a directory.

The OpenCode example has this shape.

- `workers/opencode/worker.conf` names the default model, the models that may be
  chosen, and the values `thinking=yes` and `fork=yes`.
- `workers/opencode/events.py` reads OpenCode part events and maps its tool names to
  the labels haring's readers show.
- `workers/opencode/start` names a new session, writes its id to the file given with
  `--session-file`, and runs `opencode run`.
- `workers/opencode/steer` asks the OpenCode server to deliver a message with steer
  delivery.
- `workers/opencode/stop` asks the OpenCode server to interrupt a session.
- `workers/opencode/agents-config` links `agents/<kind>.md` into
  `~/.config/opencode/agents` as `haring-<kind>.md` and asks OpenCode to reload its
  configuration.
- `workers/opencode/agents/check.md`, `errand.md`, `implement.md` and `qa.md` are the
  four OpenCode agents, one for each kind.
- `workers/opencode/api.py` builds the one `opencode api` request used by `steer` and
  `stop`.

## 2. worker.conf

`worker.conf` is plain text. The core reads one `key=value` pair per line. It has no
sections, no quotes and no comment syntax. A line the core does not recognise is
ignored.

The core reads four keys.

`default_model` is the model a fresh run uses when neither the project nor haring
itself has chosen one. The value is the model name written the way the harness takes
it.

`models` is the space-separated list of models a run may use. A model outside this
list is refused.

`thinking` is a hint that the harness can put a thought in the event stream. When it
is true, `haring-pulse` may say that a quiet worker is thinking and `haring-wait` may
print a thinking line. When it is false, those commands say only that nothing new has
arrived.

`fork` is a hint that a continued run may start a copy of the session under a new
session id. When it is true, `haring-worker` passes `--fork` to `start` on a continue.
When it is false, a continue resumes the same session.

The reading rules are exact.

- `default_model` and `models` are read from the first line that starts at column 1
  with `default_model=` or `models=`. A space before `=` hides the line. The value is
  the rest of the line.
- `thinking` and `fork` are read from any line with `=` in it. Spaces around the key
  and around the value are removed. The hint is true only when the value is exactly
  `yes`. Every other value is false. If the key appears more than once, the last line
  wins.
- `models` is split on spaces. A model name cannot contain a space.

The safe value when a line is missing or wrong:

- a missing or empty `default_model` or `models` is not replaced by a safe value. It
  is a refusal. `haring-worker` and `haring-model` stop with the message that the
  worker has no model list. `haring-meta` reads only `default_model`, so it prints
  `none` with the path when it cannot find that key.
- a `default_model` that is not in `models` makes a launch fail when the model is
  checked.
- a missing or wrong `thinking` is false.
- a missing or wrong `fork` is false.
- a missing or unreadable `worker.conf` makes both hints false, and makes any launch
  or model command fail for the missing model list.

The two hints never stop a run. The model list does.

## 3. events.py

`events.py` is loaded from the run's worker folder by file path. It is loaded once per
process and kept for later reads of the same path. The module must define three
functions with these names.

### session(event)

`session(event)` receives one decoded event object from `events.jsonl`. It returns the
session id that event names, as a string, or `None` when the event names no session.

The core uses this in `live_session` to find the session a run is working in. It reads
the event stream first, then the run's `session` file, then an older `session_id=` line
in `meta`.

### entries(event, seen)

`entries(event, seen)` receives one decoded event object and a set of part ids already
reported. It returns a list of entry objects. It returns an empty list when the event
adds nothing.

The module owns the part ids. It adds an id to `seen` when it reports that part, and
returns nothing for an id already in `seen`. The core creates the set and passes it
back unchanged. The core does not add ids itself.

An entry object is a dict with a `kind` key and the fields for that kind.

- `{"kind": "retry", "ts": <string or null>}` is one retry notice. The core counts it
  and prints an `api_retry` line on the first, second, fourth, eighth and later
  doublings.
- `{"kind": "thinking_tokens", "count": <integer>}` adds to the run's reasoning-token
  count. It prints no line.
- `{"kind": "thinking", "text": <string>, "ts": <string or null>}` is one block of the
  worker's reasoning.
- `{"kind": "says", "text": <string>, "ts": <string or null>}` is one block of the
  worker's speech.
- `{"kind": "tool", "name": <string>, "args": <object>, "ts": <string or null>}` is
  one tool call. The core renders `args` into one line. It adds
  `"error": <string>` only when the call was refused or failed.

`ts` is an ISO 8601 time string with a `Z` suffix, or `null`. The ordinary OpenCode
module makes it from the event's `timestamp` in epoch milliseconds. The core does not
require that field name; the module decides.

The core's reader uses `ts` to place each line in time. A `null` time is allowed. The
core then uses the time it read the event.

After `entries` returns, the core reads the `kind` of each entry. A tool entry is
printed under its `name`, with `args` rendered by the shared `render_args`. A
`thinking` or `says` block is printed as one block. The core keeps the ids in `seen`
for the whole run, so a part must have an id that is unique across all part kinds.

### summary(events)

`summary(events)` receives the whole stream as a list of decoded event objects. It
returns one dict with exactly these keys.

- `session`: the last session id the stream names, as a string or `None`.
- `final`: the text of the last message that carried text, as a string. An empty
  string when no message carried text.
- `error`: the text of the last error event, as a string, or `None`.
- `reason`: the reason from the last finished step, as a string, or `None`.
- `steps`: the number of finished steps, as an integer.
- `tokens`: an object with integer keys `input`, `output`, `reasoning`, `cache_read`
  and `cache_write`.
- `cost`: the sum of the step costs, as a number.
- `first`: the first event time in the stream, in epoch milliseconds, or `None`.
- `last`: the last event time in the stream, in epoch milliseconds, or `None`.

The core uses `final` and `error` to build `report.json`. When both are empty,
`haring_report.py` exits with status 2 and writes no report. It uses the other keys for
the report's counts: `session` becomes `session_id`, `steps` becomes `num_turns`,
`reason` becomes `stop_reason`, `tokens` becomes `usage`, `cost` becomes `costUSD`,
and `first` and `last` become the duration.

### Real examples

These examples come from the OpenCode run
`2026-10-30-121033-errand-14554` in the reference run folder.

The event below is shortened to the fields the functions read. Its real values are
unchanged.

    {"type": "text",
     "timestamp": 1793358638295,
     "sessionID": "ses_haring24df989f93984f43846a",
     "part": {"id": "prt_18c812c610011hnPgzZcIB31J4",
              "messageID": "msg_18c812809001ZwXIYwdjc3Rtao",
              "text": "The file rules/kinds/errand.md has 37 lines."}}

`session(event)` returns:

    "ses_haring24df989f93984f43846a"

`entries(event, set())` returns:

    [{"kind": "says",
      "text": "The file rules/kinds/errand.md has 37 lines.",
      "ts": "2026-10-30T11:10:38.295Z"}]

A real Read call from the same stream, with its event shortened the same way:

    {"type": "tool_use",
     "timestamp": 1793358637032,
     "sessionID": "ses_haring24df989f93984f43846a",
     "part": {"id": "call_1a5fefcf0d83477aba04b7b8",
              "tool": "read",
              "state": {"status": "completed",
                        "input": {"path": "rules/kinds/errand.md"}}}}

`entries(event, set())` returns:

    [{"kind": "tool",
      "name": "Read",
      "args": {"path": "rules/kinds/errand.md"},
      "ts": "2026-10-30T11:10:37.032Z"}]

`summary(events)` for the whole stream returns:

    {"session": "ses_haring24df989f93984f43846a",
     "final": "{\"task_as_i_read_it\":\"Count the lines in rules/kinds/errand.md and report the number.\",\"narrowest_reading\":\"\",\"followups\":[],\"result\":[{\"key\":\"line_count\",\"value\":\"37\"}],\"found\":true,\"where\":\"rules/kinds/errand.md\",\"redacted\":false}",
     "error": null,
     "reason": "stop",
     "steps": 3,
     "tokens": {"input": 10741,
                "output": 130,
                "reasoning": 148,
                "cache_read": 24448,
                "cache_write": 0},
     "cost": 0.0,
     "first": 1793358635752,
     "last": 1793358640596}

## 4. start, steer, stop and agents-config

The core calls each program by its full path. A program must not depend on the
current directory. `start` runs with the run's work directory as its current
directory. `steer` and `stop` run in whatever directory the manager's command runs in.

### start

The core calls `start` in three forms.

For a fresh run:

    workers/<name>/start --kind <kind> --model <model> [--effort <level>] \
        --session-file <path> <message-file>

For a continued run:

    workers/<name>/start --kind <kind> --model <model> [--effort <level>] \
        --resume <session> [--fork] <message-file>

For a report retry:

    workers/<name>/start --kind <kind> --model <model> [--effort <level>] \
        --resume <session> <message-file>

The arguments are:

- `--kind`: one of `check`, `implement`, `errand` or `qa`.
- `--model`: one model name from `worker.conf`.
- `--effort`: `low`, `high` or `max`, only when the caller asked for one.
- `--session-file`: the path where a fresh run records its session id.
- `--resume`: the session to continue.
- `--fork`: start a new session as a copy of the resumed one.
- the last argument: the path of a file that holds the whole message.

The core gives `start` no input on standard input. Standard input is `/dev/null`.
The program must not wait for input.

Standard output is the event stream. Each line must be one JSON object. The core
appends this output to the run's `events.jsonl`. A program must write nothing else to
standard output.

Standard error is for errors. The core appends it to the run's `stderr.txt`.

The exit code is the harness's own. The core does not branch on it. When `start`
fails, the run normally writes no events and no report, and the run folder is left
with an empty `report.json`.

A fresh `start` must choose a session id and write it to the `--session-file` path
before it launches the harness. The core reads that file to know the session while the
run is still going.

A continued `start` must continue the session given with `--resume`. When `--fork` is
present, it must put the continued work in a new session. The core does not pass
`--session-file` on a continue, because only the stream knows the new id.

### steer

The core calls:

    workers/<name>/steer <session> <message>

The message is one argument. It can contain spaces and newlines. The program must
deliver it to the live session and return.

The core does not read standard output. It reads standard error when the exit code is
not 0, and shows that text to the manager. The core passes no input on standard input.

Exit 0 means the session accepted the message. Exit 1 means it did not, with the
reason on standard error. Exit 2 means the call was wrong, with a usage line on
standard error.

`haring-say` is the only caller. It stops with exit 1 when `steer` returns non-zero.

### stop

The core calls:

    workers/<name>/stop <session>

The program must interrupt the session and return.

The core does not read standard output. It reads standard error when the exit code is
not 0. The core passes no input on standard input.

Exit 0 means the session was interrupted. Exit 1 means it was not, with the reason on
standard error. Exit 2 means the call was wrong, with a usage line on standard error.

`haring-kill` calls `stop` after it signals the run's process group. The stall watchdog
inside the run calls `stop` when the event stream has been silent for the stall limit.
The watchdog ignores both output and exit code.

### agents-config

The core calls:

    workers/<name>/agents-config check <kind>

`haring-worker` calls this before it creates a run folder. Exit 0 means this kind can
start here. Any other exit code stops the launch, and `haring-worker` exits 1. The
program should print the reason to standard error.

`install.sh` calls:

    workers/<name>/agents-config install

`uninstall.sh` calls:

    workers/<name>/agents-config remove

Only the installer and the uninstaller call these two forms. A non-zero exit from
`install` marks the whole install as failed. A non-zero exit from `remove` marks the
uninstall as failed.

The core gives no input on standard input and does not parse standard output or
standard error from any form. A wrong call exits 2 with a usage line on standard
error. A `check` that returns 0 while its harness is not ready lets a run start and
then fail.

## 5. What the core does when something is missing or fails

A missing `events.py` stops every command that reads the run's stream. The core prints:

    haring: no events module for worker '<name>': <path> is missing

The affected commands are `haring-wait`, `haring-pulse`, `haring-transcript`,
`haring-report`, `haring-kill` and `haring-say`. `haring-stats` does not load the
module, so it still reports what it can. A missing module stops `haring-kill` before
it signals anything.

A module that exists but fails to import raises its own traceback. The core names only
a missing file. A module without `session`, `entries` or `summary` raises
`AttributeError` when that function is called.

A missing `start` makes the runner write a "not found" error to the run's
`stderr.txt`. The runner then finds no events, writes no report, and leaves an empty
`report.json`. The run looks like a worker that stopped without reporting.

A missing `steer` makes `haring-say` exit 1 with the text of the operating system
error. A missing `stop` makes `haring-kill` end with a traceback before it writes the
`stopped` marker. The watchdog ignores a missing `stop` and still kills the run's
process group.

A missing or unusable `agents-config` stops a fresh launch with exit 1. `install.sh`
and `uninstall.sh` skip a worker folder that has no `agents-config`; `uninstall.sh
--worker <name>` does not list that folder and refuses the name with exit 2.

A missing or unreadable `worker.conf` stops a launch and `haring-model` with exit 1,
because the worker has no model list. `haring-meta` prints `none` with the path when
it cannot find a default model. The run's hints read as false.

A missing worker folder behaves the same way: no model list, no event module, no
programs.

A `start` that exits non-zero is not detected as a failure. The core records the exit
code nowhere. A `steer` or `stop` that exits non-zero is reported by the command that
called it.

## 6. How the core chooses the worker

A fresh run always uses the default worker. The default is the line
`WORKER_DEFAULT=opencode` in `bin/haring-worker`. No command-line option and no
configuration file chooses another worker for a fresh run. `haring-worker` writes the
chosen name as `worker=<name>` in the run's `meta` file before it launches anything.

A continued run uses the worker recorded in the run it continues. If that `meta` has
no `worker=` line, it uses the default worker. The new run records the same name in
its own `meta`.

Every command that reads the event stream finds the worker from the run's `meta`. It
reads the `worker=` line, or uses `opencode` when the line is absent. It then loads
`workers/<name>/events.py`. The commands that need a program call it in
`workers/<name>/`.

`haring-model` and `haring-meta` are the exception. They read the model list from
`workers/opencode/worker.conf` directly, because they answer before a run exists. They
do not use the `worker=` line.

`install.sh` walks every folder under `workers/` that has an `agents-config`. For each
one it runs `agents-config install` and marks the install as failed if that program
returns non-zero. A worker folder without `agents-config` is skipped.

`uninstall.sh` walks the same folders and runs `agents-config remove` for each one. Its
`--worker <name>` form runs only that worker's `agents-config remove`. A name that has
no folder with an `agents-config` is refused with exit 2, and the message lists the
workers that exist. The plain form removes the core's links too; the worker part is
the same loop over worker folders.
