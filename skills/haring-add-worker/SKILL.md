---
name: haring-add-worker
description: Add support for another coding-agent harness to haring. Use when the user wants haring workers to run through a harness that is not the built-in OpenCode worker, or asks to add a folder under workers/. The skill reads the harness's own documentation, builds the worker folder against WORKERS.md, and tests a real run.
---

# Add a worker harness to haring

haring starts one coding agent for each run. The code in `bin/` and `lib/` is the core.
A folder under `workers/` tells the core how to start one harness, talk to it and read
its events.

OpenCode in `workers/opencode/` is the worked example. This skill adds another worker.
It does not change the core. If this skill and `WORKERS.md` disagree, `WORKERS.md` wins,
because it describes the code as it is.

## 1. Read the contract first

Run:

    ROOT=$(haring-root)

Read `$ROOT/WORKERS.md` from the first line to the last. Read `$ROOT/workers/opencode/`
as the example. Do not copy its OpenCode commands. Copy its shape.

If `haring-root` is missing or prints nothing, stop and tell the user haring is not
installed. Do not guess where it is.

## 2. Find out how the harness works

Read the harness's own current documentation. Do not rely on memory, because harnesses
change. If the documentation is not enough, run the harness's help commands. Ask the
user only when the answer is a choice, such as which models their plan allows.

Find these facts.

- One-shot command. A command that takes one prompt, runs it, prints the result and
  exits. It must work without a terminal. This is what `start` wraps.
- Model flag. The flag or setting that chooses a model, and the exact model names. Ask
  the user which models their plan allows. These become `default_model` and `models`.
- Live event stream. A machine-readable stream that can be read while the run is going.
  It must name the session, the steps, the tool calls, the text and the end of the run.
  Find whether it carries the harness's thinking.
- Session resume and fork. The command or option that continues a session, and the one
  that starts a copy under a new id. Find the new id and where it appears.
- Preset session id. Whether the harness accepts a session id chosen before it starts.
  haring can use one to reach the session before the first event, but the session file is
  optional.
- Per-run permissions. How to run one turn with no edits, and one with no shell. The
  four kinds are `check`, `implement`, `errand` and `qa`. `check` and `qa` are read
  only. `errand` has no shell. Enforce this in the harness's own configuration or
  flags, not in the prompt.
- Steering and stop. The command or API that sends a message into a running session,
  and the one that interrupts it. Find what each returns on success and on failure.
- Login without a terminal. How the user signs in before a run. A worker has no
  terminal, and its standard input is `/dev/null`.
- Stdin. Whether the harness reads standard input before it starts. If it does, it must
  see end of file at once. The core gives it `/dev/null` for this reason.

Write the answers down. You will need them in the next step.

## 3. Build the worker folder

Create `workers/<name>/` beside `workers/opencode/`. Use the harness name, lowercase and
with no spaces. Follow `WORKERS.md` sections 1 to 4 for every file. Do not edit `bin/`
or `lib/`.

Use these files:

- `worker.conf`
- `events.py`
- `start`
- `steer`
- `stop`
- `agents-config`

Add `agents/<kind>.md` and helper modules only if the harness needs them.

`worker.conf`:

- `default_model=` one model name from the user's plan.
- `models=` every model the user may choose, separated by spaces.
- `thinking=yes` only when the event stream really carries the harness's thinking.
  Otherwise leave the line out.
- `fork=yes` only when a continue can start a copy of the session under a new id.
  Otherwise leave the line out.

Never set a hint to `yes` to make output look better. A false hint makes haring claim
something the stream does not support.

`events.py`: implement `session(event)`, `entries(event, seen)` and `summary(events)`
with the exact entry and summary shapes in `WORKERS.md` section 3. Map the harness's
tool names to the labels haring uses where they match: `Read`, `Glob`, `Grep`, `Bash`,
`Edit`, `Write`, `Patch`, `TodoWrite`. `haring-report` counts `Read`, `Glob`, `Grep`
and `Bash` as evidence. Use the harness's own name for a tool that has no match. Do not
invent a tool call that the stream does not contain.

`start`: accept the arguments in `WORKERS.md` section 4. For a fresh run, write the
session id to the `--session-file` path only when the harness accepts an id chosen up
front, and never write an id that is not the real session. For a continue, resume the
session, and fork only when `--fork` is given. Write one JSON object per line to standard
output and nothing else. Write errors to standard error. Pass the harness's exit code
through. Never read standard input.

`steer` and `stop`: use the exact arguments and exit codes in `WORKERS.md` section 4.
Return 0 only when the harness accepted the request.

`agents-config`: implement `check <kind>`, `install` and `remove`. `check` must exit 0
only when this machine can start that kind now: the harness is on `PATH`, it is signed
in, and the per-kind files are installed. Print the reason to standard error and exit
non-zero otherwise. `install` and `remove` must be safe to run again.

Do not put a model name or a harness command in `bin/` or `lib/`. The worker folder owns
them.

## 4. When the harness lacks something

Do not fake a capability. `WORKERS.md` and the core define what happens when it is
absent.

No thinking. Leave `thinking` out, or set it to a value other than `yes`. Do not emit
`thinking` or `thinking_tokens` entries. haring still shows the tool calls and the
worker's speech. `haring-wait` and `haring-pulse` do not claim the worker is thinking.
They say only that nothing new has arrived.

No fork. Leave `fork` out, or set it to a value other than `yes`. A continue resumes
the same session. The old run and the continued run share that transcript. Do not pass
`--fork` to `start`.

No steering. `haring-say` cannot deliver a message into a running session. Do not write
a `steer` that exits 0 without delivering. Either leave `steer` out, so `haring-say`
exits 1 with the operating system error, or write one that exits 1 and says the harness
cannot steer. The run itself still works. Only `haring-say` is unavailable.

No stop. `haring-kill` can still kill the run's process group, but it cannot interrupt
the session inside the harness. The session may keep working with nobody reading it.
The watchdog has the same limit. Do not write a `stop` that exits 0 without
interrupting. Write one that exits 1 with the reason instead of leaving `stop` out:
`haring-kill` then reports that reason and still writes the `stopped` marker. A missing
program is caught too, but its reason is only the operating system error. The process
group is still killed either way.

No machine-readable event stream. Stop. haring has nothing to read, so `events.py`
cannot be built and the run cannot report. Tell the user this harness cannot be a
haring worker.

## 5. Test a real run

Use a small scratch project under `/tmp`. Do not test in the user's project.

1. Run `./install.sh` in the haring root, or run the new
   `workers/<name>/agents-config install`. This installs the per-kind files.
2. Create `<project>/.haring/worker` with the new worker name in it. This is the
   project worker file from `WORKERS.md` section 6.
3. Start a small errand with `haring-worker`. Use a prompt that asks for one fact from
   one file. `haring-worker` prints the run folder. Watch it with `haring-pulse`, or
   pass `--no-pulse` for one test run.
4. Read the run with `haring-transcript <run-folder>`. Check that the tool calls, the
   speech and the thinking (if you claimed it) appear in the order they happened.
5. Read `report.json` in the run folder. Check that the final message is a report and
   that the counts and the session id are real.
6. Continue the run once. Check that a resume resumes, and that `fork=yes` starts a new
   session. Check that the old run still reads.
7. If you implemented steering or stopping, test each on a run that is still working.
   A request that returns 0 must have reached the harness.

If a check fails, fix the worker folder. Do not change the core to hide a failure.

When the run passes, tell the user the worker name, the models it uses, the capabilities
it has, the capabilities it lacks, and the run folder you tested.
