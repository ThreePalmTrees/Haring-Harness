# Haring

<br/>
<p align="center">
    <img src="Haring.png" width="200" style="display:flex;justify-self:center;"/>
</p>
<br/>
<br/>

A wrapper for using sub-agents, so you don't repeat the same setup every time.

The idea is: you have 2 different subscriptions, one is the manager, and one is the worker.

My personal setup is:
**Manager:** GitHub Copilot CLI.<br/>
**Worker:** `copilot-agent`, a Copilot CLI subagent that inherits the manager's model.

This branch's supported setup is a Copilot CLI manager with `copilot-agent` subagents by
default, or the command-line `copilot` and OpenCode workers (see
[Choose a different worker](#choose-a-different-worker)). Another worker harness can be added with the
`haring-add-worker` skill and `workers/README.md`; another manager harness with the
`haring-add-manager` skill. Other harnesses are not maintained here.

## This branch is the Copilot fork

<details>
<summary>Read how the Copilot fork works</summary>

This branch runs haring with GitHub Copilot CLI as the manager, the worker and the QA
worker. The default worker and QA worker are `copilot-agent`, subagents the manager starts
with its own `task` tool. The command-line `copilot` worker and `opencode` are the other
choices. The source agent files say `model: auto`; `agents-config install` leaves that line
out of the installed copy, so the subagent takes the manager's model, because Copilot
turns an agent-file `auto` into a named model that an auto-only plan refuses. A named
model line is kept. Start `haring-pulse --once` as an async shell command. Copilot wakes
the manager when it exits; read its output and start it again while the worker is live.
It prints only what is new, held in `pulse.pos`. Run `./install.sh` again after editing
kinds/, because the subagent copies carry the rules and schema. The Claude Code subagents
stay in the repository, but only a Claude Code manager can start them.
</details>

## Why Haring

1. Built for long-horizon work (can work autonomously)
2. Not having to repeat instructions
3. Using one subscription for everything consumes limits quickly

Manager: Plans, architects, orchestrates, and reviews.<br/>
Worker: Implements.<br/>
QA: Finds anything missed.

## Prerequisites

* A [GitHub Copilot CLI](https://docs.github.com/copilot/how-tos/copilot-cli) subscription, signed in with `copilot login`
* Optional: an [OpenCode](https://opencode.ai/console/go) subscription, only if you choose the OpenCode worker

## Install Haring

1. Clone Haring anywhere and check out this branch: `git checkout copilot`.

2. Navigate inside and run the installer:
```
cd haring-harness && ./install.sh
```
> It links the skills into `~/.claude/skills` and `~/.copilot/skills`, and install keeps a record that uninstall reads<br/>
> Haring scripts into `~/.local/bin`<br/>
> OpenCode agents into `~/.config/opencode/agents`<br/>
> `workers/copilot/agents-config` links the command-line Copilot agents into `~/.copilot/agents/haring-cli-<kind>.agent.md`.<br/>
> `workers/copilot-agent/agents-config` writes Copilot subagent copies with the rules and schema inlined; run `./install.sh` again after editing kinds/.

That's it.

## Use Haring

Just mention `/haring` in your prompt

    /haring The app is crashing. Fix it.

## What Haring writes into your project

    .haring/runs/{stamp}-{kind}-{id}/
      prompt.md      // what the worker was asked to do
      report.json    // what the worker returned
      events.jsonl   // the run's events, from the worker's own stream
      stats.txt      // model, tokens, cache reads, turns, seconds
      meta           // what the run was, so it can be continued
      PROGRESS.md    // the worker's progress, for a kind that keeps one
      stderr.txt     // only when something went wrong

    .haring/FACTS.md // short list of learned facts about the project

The first time haring writes a run into a repository it adds `.haring/` to that repository's `.gitignore`.<br/>
Nothing in there needs maintaining. It is a record, not a document.

To see every run in a project as one page, run:

```
haring-stats-page
```

It writes `stats.html` in the project's `.haring` folder and prints the path. Open that
file in a browser; the page needs no server and no network. `--out <file>` writes it
somewhere else, and naming a project writes the page for that project.

When the manager is a Claude Code session and starts a subagent while `haring-pulse` is
running, the pulse records the subagent as a run under `.haring/runs/`. When the
subagent ends, the pulse copies its transcript into the run folder and writes
`report.json` and `stats.txt` from it.

When the manager is a Copilot CLI session and starts a subagent while `haring-pulse` is
running, the pulse records it as a run the same way, from
`~/.copilot/session-state/<session>/events.jsonl`, and writes `report.json` and
`stats.txt` when it ends.

## Choose a different worker

<details>
<summary>Read how to change the worker or the QA worker (optional)</summary>

- `haring-model` prints the worker, each kind's model and where it comes from, and the
  QA worker.
- `haring-model <kind> <model>` sets that kind's model; `haring-model <kind> --clear`
  removes the setting.
- `haring-model --worker copilot-agent` makes Copilot subagents the workers for every
  project. This is the default.
- `haring-model --worker copilot` chooses the command-line Copilot worker.
- `haring-model --worker opencode` chooses OpenCode instead.
- `haring-model --worker claude` chooses the Claude Code subagent worker, which only a
  Claude Code manager can start.
- Add `--project` to any of them to write the choice for the current project only.
- `haring-model --qa <name>` does the same for the QA worker, which is `copilot-agent` by
  default.

A worker runs one of two ways. One harness is both manager and workers: a Copilot CLI
manager starts `copilot-agent` subagents by default, and a Claude Code manager starts its
own subagents. Or a manager runs another harness's command-line workers: this branch's
Copilot CLI manager can run the command-line `copilot` worker or OpenCode workers through
`haring-worker`.

Each kind's model is a line in the untracked `<haring-root>/models`, written with
`haring-model <kind> <model>` and removed with `haring-model <kind> --clear`, so
changing it leaves the repo untouched; without a line, it is the `model:` line of
`workers/<worker>/agents/<kind>.md`. For a copilot-agent subagent, `haring-model`
reinstalls the generated copy with that model in place of `auto`. The copilot-agent
source files say `model: auto`, and with no models-file line install leaves that line out
so the subagent inherits the manager's model; a named model line is kept. Copilot turns an
agent-file `auto` into a named model, which an auto-only plan refuses. The command-line
copilot worker runs every kind on `auto`; the OpenCode worker runs every kind on
`opencode-go/deepseek-v4.1-flash`; the Claude worker runs check, errand and implement on
`claude-sonnet-5-5`, and qa on `claude-opus-5-5`.

A fresh run settles its worker from `<project>/.haring/worker`, then
`<haring-root>/worker`, then `copilot-agent`; a continue keeps the worker recorded in the
run's `meta`. A QA pass runs only when you ask for one, and settles its own worker from
`<project>/.haring/qa-worker`, then `<haring-root>/qa-worker`, then `copilot-agent`; a
copilot-agent QA pass is the subagent route, an OpenCode QA worker runs as a
`haring-worker qa` run, and a Claude QA worker needs a Claude Code manager.
`workers/README.md` section 6 gives the full rule.

Another worker harness is added with the `haring-add-worker` skill and `workers/README.md`.
Another manager harness is added with the `haring-add-manager` skill.
</details>

## Uninstall Haring

<details>
<summary>Read how to uninstall Haring</summary>

To remove haring, run:

```
./uninstall.sh
```

It removes every link that points into this repository: the skill links, the Claude QA
agent, each worker's agent links and the `haring-*` scripts in `~/.local/bin`. It leaves
plain files and links to other places alone, and lists plain `haring*` files to delete by
hand. It does not touch a project's `.haring` folder or `.gitignore`.

To remove only one worker's agent links, run:

```
./uninstall.sh --worker <name>
```

It removes that worker's agent links and leaves every other link in place.
</details>

<br/>
<p align="center">
    <img src="Haring_d.png" width="200" style="display:flex;justify-self:center;"/>
</p>
<br/>

## Development and contributing

### Structure

| Folder | File | What it does |
|---|---|---|
| `installed-links` | | the record of links `install.sh` made, which `uninstall.sh` reads |
| `uninstall.sh` | | remove the links that `install.sh` made |
| `bin/` | `haring-worker` | start a worker, or continue one |
| | `haring-model` | print each kind's model and where it comes from; `<kind> <model>` writes it and `<kind> --clear` removes it; `--worker` reads or writes the worker, and `--qa` reads or writes the QA worker |
| | `haring-wait` | follow a run, then print its report |
| | `haring-pulse` | the workers' stream since the last pass, fast then at a pace you can retune |
| | `haring-kill` | stop a running worker on purpose |
| | `haring-say` | say a word to a running worker |
| | `haring-ask` | a worker's question to its manager, asked at once and answered at the worker's next turn |
| | `haring-report` | print a report, with the empty parts removed, the run's Read, Glob, Grep and Bash calls listed above it, and a warning when it made no such call |
| | `haring-transcript` | print what a run did, in the order it did it: every tool call, thought and line of speech, read from `events.jsonl` |
| | `haring-stats` | one line of numbers from a run |
| | `haring-stats-page` | write one self-contained HTML page of every run, openable from disk with no server |
| | `haring-session` | what this manager session has cost |
| | `haring-prompt` | build a worker's system prompt |
| | `haring-root` | print where haring is installed |
| `skills/haring/` | `SKILL.md` | everything the manager needs, in one file |
| `skills/haring-add-worker/` | `SKILL.md` | how to add another worker harness |
| `skills/haring-add-manager/` | `SKILL.md` | how to add another manager harness |
| `kinds/` | `rules.md` | the rules every worker gets |
| | `<kind>/rules.md` | one file per kind of task, added to `rules.md` |
| | `<kind>/schema.json` | the shape of that kind's report |
| `lib/` | `haring_events.py` | reads a run's stream for every reader |
| | `haring_report.py` | turns the stream into `report.json`, and checks the report against its schema |
| | `haring_run.py` | the numbers a run's report holds, shared by `haring-stats` and `haring-stats-page` |
| `workers/` | `README.md` | the contract a worker harness must meet, and how a run chooses its worker |
| `workers/claude/` | `events.py` | reads a Claude Code subagent's transcript and turns it into haring's entries and summary |
| | `agents-config` | install, remove and check the Claude Code agent links |
| | `agents/<kind>.md` | one Claude Code agent per kind; its `model:` line is the kind's default model |
| `workers/copilot/` | `start` | run one worker turn and write the event stream |
| | `stop` | report whether the Copilot session's process is still alive |
| | `steer` | say that a running Copilot `-p` session cannot take a message |
| | `events.py` | reads a Copilot CLI run's JSON stream and turns it into haring's entries and summary |
| | `agents-config` | install, remove and check the Copilot agent links |
| | `agents/<kind>.md` | one Copilot agent per kind; its `model:` line is that kind's model |
| `workers/copilot-agent/` | `events.py` | reads a Copilot CLI manager log's subagent lines and turns them into haring's entries and summary |
| | `agents-config` | install, remove and check the generated Copilot subagent copies, with the rules and schema inlined |
| | `agents/<kind>.md` | one Copilot subagent per kind; its `model:` line is the kind's default model |
| `workers/opencode/` | `events.py` | reads OpenCode's event stream and turns it into haring's entries and summary |
| | `start` | run one worker turn and write the event stream |
| | `steer` | send a message into a live session |
| | `stop` | interrupt a live session |
| | `agents-config` | install, remove and check the OpenCode agent links |
| | `api.py` | one request to the OpenCode server, used by `steer` and `stop` |
| | `workers/opencode/agents/check.md` | the read-only OpenCode agent for check runs |
| | `workers/opencode/agents/errand.md` | the OpenCode agent for errands; it has no shell |
| | `workers/opencode/agents/implement.md` | the OpenCode agent for implement runs |
| | `workers/opencode/agents/qa.md` | the read-only OpenCode agent for QA runs |

Everything is linked, not copied, except the generated `workers/copilot-agent/` copies,
so editing a file here takes effect at once — except an agent in
`workers/opencode/agents/<kind>.md`: the OpenCode service does not notice that edit, so
run `opencode reload` (or `./install.sh`) after one, or its old rules stay in force.
Editing a rule or a schema applies to the next worker you start, except the copilot-agent
copies: run `./install.sh` after editing kinds/, because those copies carry the rules and
schema. Editing `SKILL.md` needs a fresh manager session. Run `./install.sh` again only
when you add a script to `bin/` or move this directory.

<p align="center">
    <img src="Haring_fish.png" width="200" style="display:flex;justify-self:center;"/>
</p>

## License and responsibility

Haring is released under the [MIT License](LICENSE).

Haring is provided as is. It runs other tools (coding agents and their command-line
programs) under your own accounts. You are responsible for how you use it, and for
reading and complying with the terms of service of each tool and model provider you
connect to it.
