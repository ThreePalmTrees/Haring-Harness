---
name: haring-add-manager
description: Add support for another coding-agent harness to haring as the manager. Use when the user wants to run haring from a harness that is not Claude Code, or asks to link haring's skills into another manager. The skill measures the harness on a real run, chooses the worker routes it can carry, and says where each answer goes.
---

# Add a manager harness to haring

The manager is the agent that loads `skills/haring/SKILL.md` and runs the `haring-*`
commands. Claude Code is the manager today. This skill makes another harness a manager.

Read `WORKERS.md` for the worker contract. If this skill and `WORKERS.md` disagree,
`WORKERS.md` wins, because it describes the code as it is. `workers/opencode/` is the
worked example of a command-line worker. `workers/claude/` is the worked example of a
worker the manager starts.

## 1. Read first

Run:

    ROOT=$(haring-root)

If `haring-root` is missing or prints nothing, stop and tell the user haring is not
installed. Do not guess where it is.

Read these files in `$ROOT`:

- `WORKERS.md` sections 1, 3, "A worker the manager starts" and 6.
- `skills/haring/SKILL.md`, the whole of it. It holds the manager's instructions.
- `workers/claude/agents/*.md`, `workers/claude/agents-config` and
  `workers/claude/events.py`.
- `skill-dirs`.

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

Choose the worker and the QA worker with:

    haring-model --worker <name>
    haring-model --qa <name>

Add `--project` to write the choice for one project only. With no name, each form
prints the settled worker and where it came from.

So the mixes are: one harness as manager and workers, either as its own subagents or
through its own command-line worker; or a manager with another harness's command-line
workers. A command-line worker for the new harness is added by `skills/haring-add-worker`.
This skill points there and does not repeat it.

## 3. Measure on a real run

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
folders that hold a `SKILL.md`. Put the folder in one line of `skill-dirs`, which
`install.sh` links every folder under `skills/` into and `uninstall.sh` removes them
from. A leading `~/` means `$HOME/`; empty lines and lines starting with `#` are
ignored. Fallback: a personal instructions file that can point at
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
start `haring-pulse` as a background command and poll a run with `haring-stats` or
`haring-transcript` at the pulse cadence. Say plainly that the manager then learns of a
worker gone wrong only when it polls. A harness whose notices arrive only when a command
ends falls in this case.

**e. The manager's session id, visible to its shell commands.** Claude Code uses
`CLAUDE_CODE_SESSION_ID`. Adoption needs it in item k. Fallback: none for the subagent
route; use command-line workers.

**f. Custom subagent definitions.** Find the folder, the file name pattern, and the
frontmatter keys for name, description, tools and model. Put one file per kind at
`workers/<harness>/agents/<kind>.md`, with an `agents-config` shaped like
`workers/claude/agents-config`; `install.sh` walks every `workers/*/agents-config`.
Each kind's limits must be enforced by the harness, not by the prompt: `check` and `qa`
are read only, and `errand` has no shell. Fallback: no custom agents means no subagent
route; use command-line workers.

**g. Each kind's model.** Find whether the `model:` line takes effect. The harness's
subagent start event usually names the model and where it came from. Find which names
the user's plan accepts. A plan may accept no named model at all, only the harness's
automatic choice; then say so to the user and record it. `haring-worker` needs a
`model:` line in every agent file before a command-line launch.

**h. Starting a subagent in the background, and being told when it ends.** Claude Code
uses the Agent tool run in the background. Put the harness's form in
`skills/haring/SKILL.md`, in the section on running a manager-started agent. Fallback:
a subagent that blocks the manager still works, but nothing can be steered or watched
while it runs.

**i. Sending a message to a running subagent.** Claude Code uses SendMessage.
`haring-say` already exits 1 for a manager-started worker and tells the manager to use
its own tool. Fallback: none. Correct after the report with a continued run.

**j. Stopping a running subagent.** Claude Code uses TaskStop. Fallback: let the
subagent finish, and say so in `skills/haring/SKILL.md`.

**k. Subagent transcripts.** Find where they are written and their shape. Either there
is one file per subagent, or the subagent's lines sit inside the manager's own session
log, tagged with an agent id between a started and an ended event. Find the final
message and the token usage. Put the reader in `workers/<harness>/events.py`, with the
shapes in `WORKERS.md` section 3, including `alive()`. Put the adoption in
`bin/haring-pulse`, which today reads only Claude Code: `CLAUDE_CODE_SESSION_ID`,
`~/.claude/projects/*/<session>/subagents/`, and the functions `claude_meta_files`,
`adopt_subagents` and `finish_subagents`. This is a change to the core. Add the new
adoption beside the Claude Code one; do not replace it. When the manager and its
subagents share one session log, `events.py` must keep only the lines of that one
agent.

**l. Nesting.** A subagent must never start haring workers, and nothing marks it as
nested: `HARING_NESTED` is set only by `haring-worker`. Every agent file must say so, as
`workers/claude/agents/*.md` do.

**m. Manager cost.** `bin/haring-session` reads Claude Code transcripts under
`~/.claude/projects`. Find where the harness records per-call token usage and add a
reader, or leave `haring-session` as Claude Code only and tell the user.

**n. The default QA worker.** It is `claude` in `bin/haring-meta`, `bin/haring-model`
and `bin/haring-worker`. A fork either changes that default or writes its QA worker with
`haring-model --qa <name>`.

**o. Private paths.** `kinds/check/rules.md` and `kinds/qa/rules.md` list `~/.claude/`,
and `workers/opencode/agents/*.md` deny shell commands on `*/.claude`. Add the new
harness's own folder, with its sessions and credentials, to the rules and, where the
harness has permission rules, to its agent files.

**p. The manager's instructions.** `skills/haring/SKILL.md` names Claude Code and its
tools: the Agent tool, Monitor, `run_in_background`, SendMessage and TaskStop. In the
fork, use the new harness's names, keep every rule, and write the fallback chosen above
wherever a capability is missing. Keep the Claude Code wording when the fork keeps
Claude Code as a manager too.

**q. Skill reload.** Find whether the harness reads skills only when a session starts.
The closing lines of `install.sh` say so in general terms: editing `SKILL.md` may need a
fresh session of the manager.

## 5. Hard stops

Stop and tell the user this harness cannot be a manager when either is true:

- It has no shell.
- It has no way at all to load the manager's instructions.

## 6. Test in a scratch project

Use a small scratch project under `/tmp`. Do not test in the user's project.

1. Run `./install.sh` in the haring root.
2. Open the harness in the scratch project and start the haring skill.
3. Run `haring-meta`.
4. Start `haring-pulse`.
5. Send one small errand through each route the harness supports.
6. Follow each with `haring-wait`.
7. Check that the run folder has `report.json`, that `haring-transcript` reads the run
   in order, and that `haring-stats` shows it.

If a check fails, fix the files this skill names. Do not hide a failure by changing the
core in a way `WORKERS.md` does not describe.

## 7. Report to the user

Tell the user:

- the harness;
- the routes it supports;
- each capability from the checklist, with what the harness has or the fallback chosen;
- the files changed;
- what is left undone.
