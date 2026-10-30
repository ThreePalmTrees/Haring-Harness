# Haring

<br/>
<p align="center">
    <img src="Haring.png" width="200" style="display:flex;justify-self:center;"/>
</p>
<br/>
<br/>

A wrapper for using sub-agents, so you do not repeat the same setup every time.

**Manager:** Claude Code, on any model you pick with `/model`. `Opus` is recommended.<br/>
**Worker:** An [OpenCode](https://opencode.ai) session on `opencode-go/deepseek-v4.1-flash`
(the default) or `opencode-go/glm-5.3-flash`. Your choice, set with `haring-model`.

## Why Haring

Using Opus for everything consumes your subscription quickly, and so does an Anthropic
worker beside it.<br/>
Haring keeps Claude for the thinking and hands the legwork to a fast, cheap model.

Manager: Plans, architects, orchestrates, and reviews.<br/>
Worker: Collects details, does the coding.

## Install Haring

1. Clone this repository anywhere.

2. Install [OpenCode](https://opencode.ai) and sign in to OpenCode Go:
```
opencode auth login
```

3. Navigate inside and run the installer:
```
cd haring-harness && ./install.sh
```
> It links the skill into `~/.claude/skills`, the scripts into `~/.local/bin`, and one
> OpenCode agent per kind of worker into `~/.config/opencode/agents`.



## Use Haring

Just mention `/haring` in your prompt

    /haring The app is crashing. Fix it.

## What Haring writes into your project

    .haring/runs/{stamp}-{kind}-{pid}/
      prompt.md      what the worker was asked, the only copy of the question
      report.json    what it returned, starting with the task as the worker read it
      events.jsonl   the run's events, OpenCode's own stream as they happen
      stats.txt      model, tokens, cache reads, turns, seconds
      meta           what the run was, so it can be continued
      PROGRESS.md    written as they go, by every kind but errand
      stderr.txt     only when something went wrong

The first time haring writes a run into a repository it adds `.haring/` to that
repository's `.gitignore`. Nothing in there needs maintaining. It is a record, not a
document.

<br/>
<p align="center">
    <img src="Haring_d.png" width="200" style="display:flex;justify-self:center;"/>
</p>
<br/>

## Development and contributing

### Structure

    bin/            haring-worker    start a worker, or continue one
                    haring-model     read the worker's model, or write it —
                                    haring's own choice, or the project's
                                    with --project; --qa reads or writes
                                    the QA model the same way
                    haring-wait      follow a run, then print its report
                    haring-pulse     the workers' stream since the last pass, fast then
                                    at a pace you can retune
                    haring-kill      stop a running worker on purpose
                    haring-say       say a word to a running worker
                    haring-ask       a worker's question to its manager, asked at once
                                    and answered at the worker's next turn
                    haring-report    print a report, with the empty parts removed, the
                                    run's Read, Glob, Grep and Bash calls listed above
                                    it, and a warning when it made no such call
                    haring-transcript print what a run did, in the order it did it:
                                      every tool call, thought and line of speech,
                                      read from events.jsonl
                    haring-stats     one line of numbers from a run
                    haring-session   what this manager session has cost
                    haring-prompt    build a worker's system prompt
                    haring-root      print where haring is installed

    skills/haring/  SKILL.md         everything the manager needs, in one file

    opencode/       agents/          one OpenCode agent per kind of task; the deny
                                     rules there are what a kind may not do

    lib/            haring_events.py reads a run's stream for every reader
                    haring_report.py turns the stream into report.json, and
                                     checks the report against its schema

    rules/          worker.md        the rules every worker gets
                    kinds/           one file per kind of task, added to worker.md

    schemas/        one JSON schema per kind, the shape of that kind's report

A QA pass runs only when you ask for one. By default it runs on Opus as the Claude Code
agent `haring-qa` (`claude/agents/`, linked into `~/.claude/agents`). A project, or
haring itself, can hold a `qa-model` file naming `sonnet` or an OpenCode model instead;
the project's overrides haring's own, and an OpenCode model runs as a `haring-worker qa`
run.

Everything is linked, not copied, so editing a file here takes effect at once — except an
agent in `opencode/agents/`: the OpenCode service does not notice that edit, so run
`opencode reload` (or `./install.sh`) after one, or its old rules stay in force. Editing a
rule or a schema applies to the next worker you start. Editing `SKILL.md` needs a fresh
Claude Code session. Run `./install.sh` again only when you add a script to `bin/` or move
this directory.

<p align="center">
    <img src="Haring_fish.png" width="200" style="display:flex;justify-self:center;"/>
</p>