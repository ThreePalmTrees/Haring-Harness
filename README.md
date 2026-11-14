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
**Manager:** `Opus` via Claude Code.<br/>
**Worker:** `opencode-go/deepseek-v4.1-flash` via `OpenCode`.

This is the supported setup: a Claude Code manager with OpenCode workers. Another worker
harness can be added with the `haring-add-worker` skill and `WORKERS.md`. Other harnesses
are not maintained here.

## Why Haring

Using one subscription for everything consumes it quickly.<br/>
Haring gives you more bang for your buck.

Manager: Plans, architects, orchestrates, and reviews.<br/>
Worker: Implements.

## Install Haring

1. Install [OpenCode](https://opencode.ai) and sign in to OpenCode:
```
opencode auth login
```
_(you can exit opencode)_

2. Clone Haring anywhere.

3. Navigate inside and run the installer:
```
cd haring-harness && ./install.sh
```
> It links the skills into `~/.claude/skills`<br/>
> Haring scripts into `~/.local/bin`<br/>
> And OpenCode agents into `~/.config/opencode/agents`.

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

## Use Haring

Just mention `/haring` in your prompt

    /haring The app is crashing. Fix it.

## What Haring writes into your project

    .haring/runs/{stamp}-{kind}-{pid}/
      prompt.md      // what the worker was asked to do
      report.json    // what the worker returned
      events.jsonl   // the run's events, OpenCode's own stream as they happen
      stats.txt      // model, tokens, cache reads, turns, seconds
      meta           // what the run was, so it can be continued
      PROGRESS.md    // the worker's progress
      FACTS.md       // short list of learned facts about the project
      stderr.txt     // only when something went wrong

The first time haring writes a run into a repository it adds `.haring/` to that repository's `.gitignore`.<br/>
Nothing in there needs maintaining. It is a record, not a document.

<br/>
<p align="center">
    <img src="Haring_d.png" width="200" style="display:flex;justify-self:center;"/>
</p>
<br/>

## Development and contributing

### Structure

| Folder | File | What it does |
|---|---|---|
| `WORKERS.md` | | the contract a worker harness must meet, and how a run chooses its worker |
| `uninstall.sh` | | remove the links that `install.sh` made |
| `bin/` | `haring-worker` | start a worker, or continue one |
| | `haring-model` | read the worker's model, or write it — haring's own choice, or the project's with `--project`; `--qa` reads or writes the QA model the same way |
| | `haring-wait` | follow a run, then print its report |
| | `haring-pulse` | the workers' stream since the last pass, fast then at a pace you can retune |
| | `haring-kill` | stop a running worker on purpose |
| | `haring-say` | say a word to a running worker |
| | `haring-ask` | a worker's question to its manager, asked at once and answered at the worker's next turn |
| | `haring-report` | print a report, with the empty parts removed, the run's Read, Glob, Grep and Bash calls listed above it, and a warning when it made no such call |
| | `haring-transcript` | print what a run did, in the order it did it: every tool call, thought and line of speech, read from `events.jsonl` |
| | `haring-stats` | one line of numbers from a run |
| | `haring-session` | what this manager session has cost |
| | `haring-prompt` | build a worker's system prompt |
| | `haring-root` | print where haring is installed |
| `skills/haring/` | `SKILL.md` | everything the manager needs, in one file |
| `skills/haring-add-worker/` | `SKILL.md` | how to add another worker harness |
| `kinds/` | `rules.md` | the rules every worker gets |
| | `<kind>/rules.md` | one file per kind of task, added to `rules.md` |
| | `<kind>/schema.json` | the shape of that kind's report |
| `kinds/qa/` | `claude.md` | the Claude Code agent for the QA pass |
| `lib/` | `haring_events.py` | reads a run's stream for every reader |
| | `haring_report.py` | turns the stream into `report.json`, and checks the report against its schema |
| `workers/opencode/` | `worker.conf` | the default model and the models a worker may run on |
| | `events.py` | reads OpenCode's event stream and turns it into haring's entries and summary |
| | `start` | run one worker turn and write the event stream |
| | `steer` | send a message into a live session |
| | `stop` | interrupt a live session |
| | `agents-config` | install, remove and check the OpenCode agent links |
| | `api.py` | one request to the OpenCode server, used by `steer` and `stop` |
| | `workers/opencode/agents/check.md` | the read-only OpenCode agent for check runs |
| | `workers/opencode/agents/errand.md` | the OpenCode agent for errands; it has no shell |
| | `workers/opencode/agents/implement.md` | the OpenCode agent for implement runs |
| | `workers/opencode/agents/qa.md` | the read-only OpenCode agent for QA runs |

A fresh run settles its worker from the worker file `<project>/.haring/worker`, then
`<haring-root>/worker`, then `opencode`. A continue keeps the worker recorded in the run's
`meta`. `WORKERS.md` section 6 gives the full rule.

A QA pass runs only when you ask for one. By default it runs on Opus as the Claude Code
agent `haring-qa` (`kinds/qa/claude.md`, linked into `~/.claude/agents`). A project, or
haring itself, can hold a `qa-model` file naming `sonnet` or an OpenCode model instead;
the project's overrides haring's own, and an OpenCode model runs as a `haring-worker qa`
run.

Everything is linked, not copied, so editing a file here takes effect at once — except an
agent in `workers/opencode/agents/<kind>.md`: the OpenCode service does not notice that edit, so run
`opencode reload` (or `./install.sh`) after one, or its old rules stay in force. Editing a
rule or a schema applies to the next worker you start. Editing `SKILL.md` needs a fresh
Claude Code session. Run `./install.sh` again only when you add a script to `bin/` or move
this directory.

<p align="center">
    <img src="Haring_fish.png" width="200" style="display:flex;justify-self:center;"/>
</p>