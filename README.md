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
**Worker:** opencode-go/deepseek-v4.1-flash via `OpenCode`.

This is the supported setup: a Claude Code manager with OpenCode workers, or with
Claude Code subagents as workers (`haring-model --worker claude`). Another worker
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
| | `haring-model` | print each kind's model and its agent file; `--worker` reads or writes the worker, and `--qa` reads or writes the QA worker |
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
| `kinds/` | `rules.md` | the rules every worker gets |
| | `<kind>/rules.md` | one file per kind of task, added to `rules.md` |
| | `<kind>/schema.json` | the shape of that kind's report |
| `lib/` | `haring_events.py` | reads a run's stream for every reader |
| | `haring_report.py` | turns the stream into `report.json`, and checks the report against its schema |
| | `haring_run.py` | the numbers a run's report holds, shared by `haring-stats` and `haring-stats-page` |
| `workers/claude/` | `worker.conf` | the hints and route texts a Claude Code worker declares |
| | `events.py` | reads a Claude Code subagent's transcript and turns it into haring's entries and summary |
| | `agents-config` | install, remove and check the Claude Code agent links |
| | `agents/<kind>.md` | one Claude Code agent per kind; its `model:` line is that kind's model |
| `workers/opencode/` | `worker.conf` | the hints a worker declares |
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

Every kind's model is the `model:` line of `workers/<worker>/agents/<kind>.md`. The
OpenCode worker runs every kind on `opencode-go/deepseek-v4.1-flash`; the Claude worker
runs check, errand and implement on `claude-sonnet-5-5`, and qa on `claude-opus-5-5`.

A QA pass runs only when you ask for one. The QA worker settles from
`<project>/.haring/qa-worker`, then `<haring-root>/qa-worker`, then `claude`. By default
that is the Claude worker, whose `workers/claude/agents/qa.md` names `claude-opus-5-5`
on its `model:` line. The project's QA worker file overrides haring's own. An OpenCode
QA worker runs as a `haring-worker qa` run.

Everything is linked, not copied, so editing a file here takes effect at once — except an
agent in `workers/opencode/agents/<kind>.md`: the OpenCode service does not notice that edit, so run
`opencode reload` (or `./install.sh`) after one, or its old rules stay in force. Editing a
rule or a schema applies to the next worker you start. Editing `SKILL.md` needs a fresh
Claude Code session. Run `./install.sh` again only when you add a script to `bin/` or move
this directory.

<p align="center">
    <img src="Haring_fish.png" width="200" style="display:flex;justify-self:center;"/>
</p>