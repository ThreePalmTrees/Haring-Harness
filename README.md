# Haring

<br/>
<p align="center">
    <img src="Haring.png" width="200" style="display:flex;justify-self:center;"/>
</p>
<br/>
<br/>

A wrapper for using sub-agents, so you do not repeat the same setup every time.

**Manager:** Any model. `Opus` is recommended.<br/>
**Worker:** `GLM-5.3-Flash`. You can ask the manager to use a different model.

## Why Haring

Using Opus for everything consumes your subscription quickly.<br/>
Haring gives you more bang for your buck.

Manager: Plans, architects, orchestrates, and reviews.<br/>
Worker: Collects details, does the coding.

## Install Haring

1. Clone this repository anywhere.

2. Navigate inside and Run the installer:
```
cd haring-harness && ./install.sh
```

3. Add your Z.ai API key to macOS Keychain:
```
security add-generic-password -a "$USER" -s haring-zai -U -w
```
> The terminal will prompt you for the key. The key stays out of your shell history.



## Use Haring

Just mention `/haring` in your prompt

    /haring The app is crashing. Fix it.

## What Haring writes into your project

    .haring/runs/{stamp}-{kind}-{pid}/
      prompt.md      what the worker was asked, the only copy of the question
      report.json    what it returned, starting with the task as the worker read it
      events.jsonl   the run's events, written by haring as they happen
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
                    haring-wait      follow a run, then print its report
                    haring-pulse     the workers' stream since the last pass, fast then
                                    at a pace you can retune
                    haring-kill      stop a running worker on purpose
                    haring-say       say a word to a running worker
                    haring-ask       a worker's question to its manager, asked at once
                                    and answered at the worker's next turn
                    haring-report    print a report, with the empty parts removed, and warn
                                    when the worker made no Read, Glob, Grep or Bash call
                    haring-transcript print what a run did, in the order it did it:
                                      every tool call, thought and line of speech,
                                      read from events.jsonl
                    haring-stats     one line of numbers from a run
                    haring-session   what this manager session has cost
                    haring-prompt    build a worker's system prompt
                    haring-root      print where haring is installed

    skills/haring/  SKILL.md         everything the manager needs, in one file

    rules/          worker.md        the rules every worker gets
                    kinds/           one file per kind of task, added to worker.md

    schemas/        one JSON schema per kind, the shape of that kind's report

Everything is linked, not copied, so editing a file here takes effect at once. Editing a
rule or a schema applies to the next worker you start. Editing `SKILL.md` needs a fresh
Claude Code session. Run `./install.sh` again only when you add a script to `bin/` or move
this directory.

<p align="center">
    <img src="Haring_fish.png" width="200" style="display:flex;justify-self:center;"/>
</p>