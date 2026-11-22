---
name: haring-add-manager
description: Add support for another coding-agent harness to haring as the manager. Use when the user wants to run haring from a harness that is not Claude Code, or asks to link haring's skills into another manager. The skill measures the harness on a real run, chooses the worker routes it can carry, and says where each answer goes.
---

# Add a manager harness to haring

The manager is the agent that loads `skills/haring/SKILL.md` and runs the `haring-*`
commands. Claude Code is the manager today. This skill makes another harness a manager.

Read `workers/README.md` for the worker contract. If this skill and `workers/README.md` disagree,
`workers/README.md` wins, because it describes the code as it is. `workers/opencode/` is the
worked example of a command-line worker. `workers/claude/` is the worked example of a
worker the manager starts.

## 1. Read first

Run:

    ROOT=$(haring-root)

If `haring-root` is missing or prints nothing, stop and tell the user haring is not
installed. Do not guess where it is.

Read these files in `$ROOT`:

- `workers/README.md` sections 1, 3, "A worker the manager starts" and 6.
- `skills/haring/SKILL.md`, the whole of it. It holds the manager's instructions.
- `workers/claude/agents/*.md`, `workers/claude/agents-config` and
  `workers/claude/events.py`.
- `install.sh`, for its skills loop.

## 2. Know what a manager is

A manager has two ways to run a worker.

A command-line worker is a folder at `workers/<name>/` with a `start` program.
`haring-worker` starts it as a process of its own. `workers/opencode/` is the example.
Any manager can use it, so a manager of one harness can run another harness's
command-line workers.

A manager-started worker is a subagent of the manager's own session. The manager starts
it with its own tool, and `haring-pulse` adopts it as a run and reads the transcript it
writes. `workers/claude/` is the example. This route exists only when the manager and
the worker are the same harness.

Choose a kind's driver with:

    haring-worker-driver --kind <kind> --driver <driver>
    haring-worker-driver --driver <driver>

Add `--project` to write the choice for one project only. With no argument it prints
each kind's driver.

So the mixes are: one harness as manager and workers, either as its own subagents or
through its own command-line worker; or a manager with another harness's command-line
workers. A command-line worker for the new harness is added by `skills/haring-add-worker`.
This skill points there and does not repeat it.

Build the subagent route first when the harness can start its own subagents from agent
files. That route is the goal of making the harness both manager and worker; make it the
fork's default driver, qa included. The command-line worker is an optional extra: it is
how this harness serves as a worker under another manager, never a substitute for the
subagent route. The adoption in `bin/haring-pulse` is a core change this skill expects
and allows; needing it is not a reason to leave the route out.

## 3. Measure on a real run

Read the harness's own current documentation and its help commands first. Do not rely
on memory, because harnesses change. The run below checks what the documentation says.

Make a scratch git repository under `/tmp`. Never measure in the user's project.

Run the harness's one-shot mode with its machine-readable output. Give it a session id
up front if it accepts one, and give it `/dev/null` on standard input so it never waits
for a terminal.

In the prompt, ask the model to do five things:

1. Print the names, never the values, of its environment variables that mention the
   harness or a session.
2. List the exact names of the tools it holds.
3. Start a custom agent defined in the scratch repository, once normally and once in the
   background.
4. Send that running agent one message.
5. Start one shell command in the background and say whether it is told when the command
   ends.

Then read the harness's own session log on disk. The model's account of what it did is
not evidence. The log is.

A run costs the user's plan. Keep the probes few and small. Ask the user only for
choices, such as which models their plan allows. At the end, say what the probes left
behind: sessions, the scratch folder, and anything else.

## 4. The checklist

For each item, find the answer, put it where the item says, and take the fallback when
the harness has nothing there.

**a. Skill folder.** Find where the harness reads personal skills, and whether it reads
folders that hold a `SKILL.md`. Write that folder into the skills loop in `install.sh`,
beside `$HOME/.claude/skills`. Uninstall needs no change, because it reads the record
`install.sh` writes. Fallback: a personal instructions file that can point at
`skills/haring/SKILL.md`. With neither, stop: the harness cannot be a manager.

**b. Shell.** The manager must run shell commands and find the `haring-*` commands on
`PATH`. Missing: stop.

**c. A background command that says when it ends.** Claude Code uses the Bash tool's
`run_in_background`. Put the harness's form in `skills/haring/SKILL.md`, where the
manager starts `haring-wait`. Fallback: poll with `haring-stats <run>`, which exits 3
while the worker is alive, at the pulse's pace. Say in the file that each poll costs a
turn.

**d. A wake-up on each output line of a running command.** Claude Code uses the Monitor
tool, and that is how `haring-pulse` reaches the manager mid-run. `haring-worker` refuses
to launch while no pulse watches the project, so the pulse must run anyway. Fallback:
add a one-pass mode to `haring-pulse`, such as `--once`. It waits for a first worker as a
normal pulse does, exits after the first pass that printed something, and saves each
run's reader position in the run folder; the next one-pass pulse starts from there and
prints only what is new. The manager starts it as a background command before the worker
and starts it again each time the end of that command wakes it while a run is live. Use
`haring-stats` as a check, not as the poll. Say plainly that the manager then learns of a
worker gone wrong only when the command ends. A harness whose notices arrive only when a
command ends falls in this case.

**e. The manager's session id, visible to its shell commands.** Claude Code uses
`CLAUDE_CODE_SESSION_ID`. Adoption needs it in item l. Fallback: none for the subagent
route; use command-line workers.

**f. Custom subagent definitions.** Find the folder, the file name pattern, and the
frontmatter keys for name, description, tools and model. Put one file per kind at
`workers/<harness>/agents/<kind>.md`, with an `agents-config` shaped like
`workers/claude/agents-config`; `install.sh` walks every `workers/*/agents-config`.
Each kind's limits must be enforced by the harness, not by the prompt: `check` and `qa`
are read only, and `errand` has no shell. Subagent agent files and command-line worker
agent files usually live in the same agent folder of the harness, so give them different
names: keep `haring-<kind>` for the subagents and use another prefix for the command-line
worker. Fallback: no custom agents means no subagent route; use command-line workers.

**g. Files outside the project.** Test with a real subagent whether it can read haring's
own files, `$ROOT/kinds/rules.md` and the kind's rules and schema, without a permission
prompt. If it cannot, install generated copies of the agent files instead of links, with
the rules (`bin/haring-prompt <kind>`) and the kind's schema written in. Put a marker
naming the source in each copy, so `remove` deletes only its own copies, and have `check`
report a copy that is out of date. Say that `./install.sh` must be run again after editing
`kinds/`.

**h. Each kind's model.** Find whether the `model:` line takes effect. The harness's
subagent start event usually names the model and where it came from. Find which names
the user's plan accepts. A plan may accept no named model at all, only the harness's
automatic choice; then say so to the user and record it. A model the plan refuses makes
the subagent fail as it starts. A harness may turn an automatic-model value written in
an agent file into a named model, which a plan that refuses named models then rejects.
In that case leave the model line out of the installed copy, so the subagent runs on the
manager's model; a named model written by the user stays. `haring-worker` needs a
`model:` line in every agent file before a command-line launch.

**i. Starting a subagent in the background, and being told when it ends.** Claude Code
uses the Agent tool run in the background. Put the harness's form in
`skills/haring/SKILL.md`, in the section on running a manager-started agent. Fallback:
a subagent that blocks the manager still works, but nothing can be steered or watched
while it runs.

**j. Sending a message to a running subagent.** Claude Code uses SendMessage.
`haring-say` already exits 1 for a manager-started worker and tells the manager to use
its own tool. Fallback: none. Correct after the report with a continued run.

**k. Stopping a running subagent.** Claude Code uses TaskStop. Fallback: let the
subagent finish, and say so in `skills/haring/SKILL.md`.

**l. Subagent transcripts.** Find where they are written and their shape. Either there
is one file per subagent, or the subagent's lines sit inside the manager's own session
log, tagged with an agent id between a started and an ended event. Find the final
message and the token usage. Put the reader in `workers/<harness>/events.py`, with the
shapes in `workers/README.md` section 3, including `alive()`. Put the adoption in
`bin/haring-pulse`, which today reads only Claude Code: `CLAUDE_CODE_SESSION_ID`,
`~/.claude/projects/*/<session>/subagents/`, and the functions `claude_meta_files`,
`adopt_subagents` and `finish_subagents`. This is a change to the core. Add the new
adoption beside the Claude Code one; do not replace it. When the manager and its
subagents share one session log, create the run only once both the subagent's start
event and its first prompt line are in the log. Write a real `events.jsonl` that holds
only that agent's lines and only ever grows, because the readers follow it by byte
position. Remember a byte offset into the shared log instead of reading the whole log on
every pass, because a manager's log grows for the whole session and the pulse looks
every second.

**m. Nesting.** A subagent must never start haring workers, and nothing marks it as
nested: `HARING_NESTED` is set only by `haring-worker`. Every agent file must say so, as
`workers/claude/agents/*.md` do.

**n. Manager cost.** `bin/haring-session` reads Claude Code transcripts under
`~/.claude/projects`. Find where the harness records per-call token usage and add a
reader, or leave `haring-session` as Claude Code only and tell the user.

**o. The default qa driver.** It is `claude` in `bin/haring-meta`, `bin/haring-model`,
`bin/haring-worker` and `bin/haring-worker-driver`. A fork either changes that default
or sets the qa kind's driver with `haring-worker-driver --kind qa --driver <name>`.

**p. Private paths.** `kinds/check/rules.md` and `kinds/qa/rules.md` list `~/.claude/`,
and `workers/opencode/agents/*.md` deny shell commands on `*/.claude`. Add the new
harness's own folder, with its sessions and credentials, to the rules and, where the
harness has permission rules, to its agent files.

**q. The manager's instructions.** `skills/haring/SKILL.md` names Claude Code and its
tools: the Agent tool, Monitor, `run_in_background`, SendMessage and TaskStop. In the
fork, use the new harness's names, keep every rule, and write the fallback chosen above
wherever a capability is missing. Keep the Claude Code wording when the fork keeps
Claude Code as a manager too.

**r. Skill reload.** Find whether the harness reads skills only when a session starts.
The closing lines of `install.sh` say so in general terms: editing `SKILL.md` may need a
fresh session of the manager.

## 5. Hard stops

Stop and tell the user this harness cannot be a manager when either is true:

- It has no shell.
- It has no way at all to load the manager's instructions.

## 6. Test in a scratch project

Use a small scratch project under `/tmp`. Do not test in the user's project.

1. Run `./install.sh` in the haring root.
2. Open the harness in the scratch project in an interactive session, and start the
   haring skill. One-shot mode can wait for background work differently, so it is not
   enough.
3. Run `haring-meta`.
4. Start `haring-pulse`, or its one-pass mode when the harness has no wake-up per line.
5. Send one small errand through each route the harness supports.
6. Follow each with `haring-wait`.
7. Follow one subagent worker end to end: `haring-pulse` adopts it, the pulse or the
   one-pass poll shows it, `haring-wait` follows it, and `report.json` is a valid report
   of the kind's schema.
8. Check that the run folder has `report.json`, that `haring-transcript` reads the run
   in order, and that `haring-stats` shows it.

If a check fails, fix the files this skill names. Do not hide a failure by changing the
core in a way `workers/README.md` does not describe.

## 7. Report to the user

Tell the user:

- the harness;
- the routes it supports;
- each capability from the checklist, with what the harness has or the fallback chosen;
- the files changed;
- what is left undone.

Say "the harness lacks X" only when a measured run showed it. Something haring has no
code for yet is work to do, not a limit: build it or ask the user before leaving it out.
Each answer about a message to a running worker, a stop or a wake-up names the run or log
line that settled it.
