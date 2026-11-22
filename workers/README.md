# Worker contract

haring has two parts.

The core is `bin/` and `lib/`. It starts runs, reads their event streams, builds
reports, watches live runs, steers them and stops them.

A worker is everything under `workers/<name>/`. It knows one coding-agent harness:
how to start it, how to send a message to it, how to stop it, and what its event
stream means. A worker the manager starts with its own tools may leave out the start,
steer and stop programs; the core then reads the transcript those tools write and tells
the manager to use its own tools.

The core calls the worker folder by path. It does not import the harness and does not
read the harness's own configuration. This file describes what a worker folder must
provide and what the core does with it today. `workers/opencode/` is the worked
example for a worker with its own programs; `workers/claude/` is the worked
example for one the manager starts.

## 1. What a worker folder is

A worker folder lives at `workers/<name>/` under the haring root. A fresh run settles
its kind's driver from `<project>/.haring/drivers`, then `<haring-root>/drivers`, then
the default: `copilot-agent` for every kind.
A continued run uses the `worker=` line in the run it continues, or `copilot-agent` when
that line is absent. Section 6 gives the full rule.

The core uses these files.

- `events.py` is a Python module with three functions. Every command that reads a
  run's event stream loads it.
- `start` is optional. When present, it runs one worker turn and writes the event
  stream. A worker the manager starts with its own tools has none.
- `steer` is optional. When present, it delivers a message into a live session.
- `stop` is optional. When present, it interrupts a live session.
- `agents-config` installs, removes and checks the worker's harness-side files.
  `haring-worker` calls its `check` before a launch, and the installers call `install`
  and `remove`. A worker the manager starts does not need it.
- `agents/<kind>.md` is one file per kind. Its `model:` line is the kind's default
  model; a line for that worker and kind in `<haring-root>/models` wins, and the core
  reads it before it launches the kind. The worker's own `agents-config` installs the
  file into the harness, as a generated copy when the models file sets the model.
- `api.py` is a helper module used by the OpenCode `steer` and `stop`. The core never
  reads it.

A worker folder may hold other files. The core ignores them.

A program that is present must be executable. `events.py` must be readable.

The OpenCode example has this shape.

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

The Claude Code example has this shape. The manager starts it with Claude Code's Agent
tool, and haring reads the transcript the subagent writes.

- `workers/claude/events.py` reads a subagent transcript and turns its user and
  assistant turns into haring's entries and summary.
- `workers/claude/agents-config` links `agents/<kind>.md` into `~/.claude/agents`
  as `haring-<kind>.md`.
- `workers/claude/agents/check.md`, `errand.md`, `implement.md` and `qa.md` are
  the four Claude Code agents, one for each kind.
- It has no `start`, `steer` or `stop`. The manager starts the subagent with the Agent
  tool, steers it with SendMessage and stops it with TaskStop. `haring-pulse` adopts
  the subagent as a run, and the run has no pid, so its liveness comes from the
  module's `alive()` function.

## 2. Thinking, fork and steering

The core decides these from the worker folder's programs and from the run's event stream.
No file in the worker folder configures them.

`thinking`: a reader claims the worker is thinking only when the stream has carried a
thought — a `thinking` entry, or a reasoning-token count above 0. `haring-wait` and
`haring-pulse` print their thinking line on that evidence alone. A worker whose stream
has not carried a thought yet gets the plain "nothing new" line instead, with no claim
about thinking.

`fork`: a continued run always asks the worker's `start` program to fork, passing
`--fork`. A `start` program that cannot fork resumes the same session instead, so the
run it continues and the new run share that transcript.

`steer` and `stop`: a worker the manager starts with its own tools has neither program.
`haring-say` and `haring-kill` then reach nothing. They exit 1 with one line, the same
for every worker, saying this worker has no steer (or stop) program and the manager
steers (or stops) it with its own tools. When the run's `meta` has an `agent_id`, the
line ends with that id in parentheses.

## 3. events.py

`events.py` is loaded from the run's worker folder by file path. It is loaded once per
process and kept for later reads of the same path. The module must define three
functions with these names. A worker whose runs carry no pid in `meta` may also define
`alive(run, meta)`, described after the three.

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

The core uses `final` and `error` to build `report.json`. It uses the other keys for
the report's counts: `session` becomes `session_id`, `steps` becomes `num_turns`,
`reason` becomes `stop_reason`, `tokens` becomes `usage`, `cost` becomes `costUSD`,
and `first` and `last` become the duration.

For a known kind without `--no-answer`, when the final message and the error text are
both empty, `haring_report.py` exits with status 2 and writes no report. The no-schema
mode — a schema file of `-`, or no schema argument — writes the final text as a success
with no `structured_output`; a run with no answer gets one error report with an empty
result. `--no-answer` writes that error report instead of exiting 2. `haring-pulse` uses
the no-schema mode for an adopted subagent of an unknown kind, and `--no-answer` for an
adopted run that ended with no answer.

### alive(run, meta)

A run's `meta` names a pid when the core started the worker as a process of its own.
When it does not, the core asks the run's worker module whether the run is still going:
a module that defines `alive(run, meta)` answers, and the run is alive only when that
function returns True. A module without the function cannot say a pid-less run is alive,
so the run reads as ended. `workers/claude/events.py` answers from the sidecar
meta file Claude Code writes beside a subagent transcript, which carries `"finished":
true` once the subagent has ended. The module also reads a transcript that has not been
written for fifteen minutes as ended, because a Claude Code session that dies
mid-subagent never writes that flag.

The core's one liveness function is `run_alive` in `lib/haring_events.py`. It uses
`run_pid_alive` when `meta` has a pid, and calls the module's `alive(run, meta)` when it
has none.

### started=

A run that haring starts as a process has no `started=` line in `meta`; its meta file's
own time is its start. `haring-pulse` writes `started=` when it adopts a subagent whose
transcript began earlier than the run folder. `run_started` in `lib/haring_events.py`
reads that value when it is there, and falls back to the meta file's time when it is
not. `haring-transcript`, `haring-wait`, `haring-pulse`, `haring-stats-page` and the
duration in `report.json` measure from `run_started`.

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
- `--model`: the model this kind runs on, from `<haring-root>/models` when it has a line
  for the driver and kind, else the `model:` line of the driver's `agents/<kind>.md`, or
  the caller's one-run override.
- `--effort`: `low`, `high` or `max`, only when the caller asked for one.
- `--session-file`: the path where a fresh run may record its session id.
- `--resume`: the session to continue.
- `--fork`: start a new session as a copy of the resumed one; a `start` that cannot
  fork ignores it and resumes the session.
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

A fresh `start` may write the session id to the `--session-file` path before it launches
the harness. This is optional. Write it only when the harness accepts a session id chosen
up front, and never write an id that is not the real session. The core reads the event
stream first and the file second. Without the file, `haring-say` and `haring-kill` cannot
reach the session until the first event names it.

A continued `start` must continue the session given with `--resume`. When `--fork` is
present, it must put the continued work in a new session; a `start` that cannot fork
ignores `--fork` and resumes the same session. The core does not pass
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

### A worker the manager starts

Some harnesses run inside the manager's own session. The manager starts the work with
the harness's tool, and haring only reads the transcript. `workers/copilot-agent/` and
`workers/claude/` are the examples.

Such a worker leaves out `start`, `steer` and `stop`. `haring-worker` refuses to launch
it: when the settled driver has no `start` program it exits 2, names the missing path,
and creates no run folder. A Copilot CLI manager starts a `copilot-agent` with the `task`
tool and steers it with `write_agent`; no Copilot tool stops a running subagent, so
`haring-kill` and `haring-say` exit 1 for one and name the agent id. A Claude Code manager
starts a `claude` subagent with its own Agent tool, steers it with SendMessage and stops
it with TaskStop.

When a worker has no `steer` or `stop`, `haring-say` and `haring-kill` do not try to
reach it. They exit 1 with one line, the same for every worker: this worker has no
steer (or stop) program, and the manager steers (or stops) it with its own tools. When
the run's `meta` has an `agent_id`, the same line ends with that id in parentheses.

`haring-pulse` records the subagents of its own Claude Code session as runs. It looks
only in the session named by `CLAUDE_CODE_SESSION_ID`, under the folder named by
`HARING_CLAUDE_PROJECTS` or, when that is unset, `~/.claude/projects`. Without a session
id it adopts nothing and says so once.

The pulse scans the runs folder once each pass and keeps what it learned about a run. A
run that has reported, whose worker is gone, or whose worker module cannot be loaded is
not read again by that pulse: no meta is parsed and no worker module is loaded. A run
whose module cannot be loaded gets one warning naming the run and the file, and the pulse
keeps reporting the other runs.

For each subagent the pulse creates
`<project>/.haring/runs/<stamp>-<kind>-<agent id>/`. Its `meta` holds `kind`,
`workdir`, `model`, `worker=claude`, `agent_id`, `agent_type`, `transcript` and
`started`. Its `prompt.md` holds the first user message. Its `events.jsonl` is a link to
the transcript. A subagent still going is reported like any other live run.

When the subagent has ended, the pulse replaces the link with a copy of the transcript,
writes `report.json`, and writes `stats.txt` with `haring-stats`. A known kind is checked
against `kinds/<kind>/schema.json`; a report that does not match is kept as the raw final
text with `--final`. An unknown kind gets a report with the raw final text and no schema.
A run that ended with no answer gets one error report saying so.

The run has no pid. Its liveness comes from the worker module's `alive()`, which reads
the `"finished"` flag in the sidecar meta file beside the transcript. A transcript not
written for fifteen minutes also reads as ended, so a session that dies mid-subagent does
not leave a run live for ever; such a run is finished as any other ended run is.

A pulse with `COPILOT_AGENT_SESSION_ID` set does the same for Copilot CLI subagents,
beside the Claude Code adoption. It reads the manager's log at
`$HARING_COPILOT_STATE/<session>/events.jsonl`, where `HARING_COPILOT_STATE` defaults to
`$COPILOT_HOME/session-state` or `~/.copilot/session-state`. Each `subagent.started` with
a `user.message` becomes `<project>/.haring/runs/<stamp>-<kind>-<agent id>/`, with
`worker=copilot-agent` and the started event's time. Its `events.jsonl` is a real file
holding only that agent's lines, appended in log order as the log grows; it is never a
copy of the whole session log. An ended Copilot run is finished with `report.json` and
`stats.txt` and no copy step. Its liveness comes from `workers/copilot-agent/events.py`
`alive()`, which reads the same log for that agent's `subagent.completed` or
`subagent.failed` line and reads a log not written for fifteen minutes as ended.

A pulse started with `--once` is a poll. It exits 0 after the first pass that printed
anything, and otherwise exits as a plain pulse does: when the workers it took on have
ended, or about two minutes after starting if none appeared. It writes each live run's reader
byte position to `<run>/pulse.pos` on exit, and a later `--once` starts its reader there,
so a restarted poll prints only what is new. Without `--once` the pulse keeps its cadence,
output and exit as before.

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
`haring-report`, `haring-kill` and `haring-say`. `haring-stats` loads the module only for
a run with no pid and no report, because a pid-less live run is the one its worker has to
answer for; a run with a pid is read without the module and still reports what it can. A missing module stops `haring-kill` before
it signals anything. On a run, a worker with no `events.py` makes `lib/haring_report.py`
exit 1, which the launcher reads as a bad report and retries twice before `--final`.

A module that exists but fails to import raises its own traceback. The core names only
a missing file. A module without `session`, `entries` or `summary` raises
`AttributeError` when that function is called.

A missing `start` stops a launch before the run folder exists: `haring-worker` exits 2
and names the path. A worker the manager starts with its own tools has no `start`
program; the manager starts it with the Agent tool instead.

A missing `steer` makes `haring-say` exit 1 before waiting, with the line that says this
worker has no steer program and the manager steers it with its own tools, followed by
the run's `agent_id` from `meta` when there is one. A missing `stop` makes `haring-kill`
exit 1 before it signals anything, with the same line for stop; it writes no `stopped`
marker. The watchdog ignores a missing `stop`'s output and exit code and still kills the
run's process group.

A missing or unusable `agents-config` stops a fresh launch with exit 1. `install.sh`
and `uninstall.sh` skip a worker folder that has no `agents-config`; `uninstall.sh
--worker <name>` does not list that folder and refuses the name with exit 2.

A fresh launch stops with exit 2 and names the agent file when `<haring-root>/models`
has no line for the driver and kind and `agents/<kind>.md` is missing or has no `model:`
line. `haring-meta` prints `none` with the agent file path when it cannot find a kind's
model.

A missing worker folder makes `haring-worker` stop with exit 2 before it creates the
run folder. A run whose `meta` names a worker folder that has since been removed has no
event module and no programs, so its readers fail on the missing `events.py`.

A `start` that exits non-zero is not detected as a failure. The core records the exit
code nowhere. A `steer` or `stop` that exits non-zero is reported by the command that
called it.

## 6. How the core chooses the driver

A fresh run settles its kind's driver from two files. It reads the last line for the
kind in `<project>/.haring/drivers`, then in `<haring-root>/drivers`; the project file
wins when it names the kind. A drivers file holds one `<kind> <driver>` per line; blank
lines and lines whose first word starts with # are ignored, and the last line for a kind
wins. When neither file names the kind, the default is `copilot-agent` for every kind.

The settled name must be a folder under `workers/`. When it is not, `haring-worker`
stops before it creates the run folder. It exits 2, prints where the name came from,
and lists the worker folders that exist. A default name with no folder is refused the
same way.

`haring-worker` writes the chosen name as `worker=<name>` in the run's `meta` file
before it launches anything.

A continued run uses the worker recorded in the run it continues. If that `meta` has
no `worker=` line, it uses `copilot-agent`. The new run records the same name in its own
`meta`. A missing worker folder is refused the same way, with the run's `meta` named as
the source.

Every command that reads the event stream finds the driver from the run's `meta`. It
reads the `worker=` line, or uses `copilot-agent` when the line is absent. It then loads
`workers/<name>/events.py`. The commands that need a program call it in
`workers/<name>/`.

`haring-model` and `haring-meta` answer before a run exists. They settle each kind's
driver the same way a fresh run does: `<project>/.haring/drivers`, then
`<haring-root>/drivers`, then `copilot-agent` for every kind. Each kind's model is its
line in `<haring-root>/models`, else the `model:` line of
`workers/<driver>/agents/<kind>.md`. `haring-meta` prints one line, `Drivers and
models: ...`, with every kind's driver and model.

`haring-worker-driver` prints each kind's driver. `--kind <kind> --driver <driver>`
sets one kind and `--driver <driver>` sets all four; `--project` writes
`<project>/.haring/drivers` instead of `<haring-root>/drivers`. A name with no folder
under `workers/` is refused.

A fresh run's model is the line for its driver and kind in `<haring-root>/models`, else
the `model:` line of `workers/<driver>/agents/<kind>.md`. It is read after the driver
settles and before the run folder is created. The models file is untracked, so changing
a model there leaves the repo untouched. A missing model in both stops the launch with
exit 2 and names the agent file. `haring-worker --model` is a one-run override, passed
through unchecked, and a continue keeps the model recorded in the run it continues.

`haring-model` with no argument prints each kind's driver, its model and where the model
came from. `haring-model --worker <name> --kind <kind> --model <model>` writes that
worker's model for that kind into `<haring-root>/models`, and `--clear` in place of
`--model` removes it; for a copilot-agent subagent the generated copy is reinstalled with
that model in place of `auto`, and for the Claude driver the agent is reinstalled as a
generated copy carrying the model. When the kind settles to a different driver, the write
also prints a note naming it.

`install.sh` walks every folder under `workers/` that has an `agents-config`. For each
one it runs `agents-config install` and marks the install as failed if that program
returns non-zero. A worker folder without `agents-config` is skipped.

`uninstall.sh` walks the same folders and runs `agents-config remove` for each one. Its
`--worker <name>` form runs only that worker's `agents-config remove`. A name that has
no folder with an `agents-config` is refused with exit 2, and the message lists the
workers that exist. The plain form removes the core's links too; the worker part is
the same loop over worker folders.
