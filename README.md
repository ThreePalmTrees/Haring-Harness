# Haring

<br/>
<img src="Haring.png" width="200"/>
<br/>
<br/>

A wrapper for using sub-agents, so you do not repeat the same setup every time.

**Manager model:** any Anthropic model. Opus is recommended.
**Worker model:** GLM-5.3-Flash by default. You can ask the manager to use a different one.

## Install

**1. Add your Z.ai API key.** On macOS it goes in the Keychain:

    security add-generic-password -a "$USER" -s haring-zai -U -w

Put `-w` last with no value, so it prompts for the key and the key stays out of your
shell history.

**2. Clone this repository anywhere.**

**3. Run the installer from inside it:**

    cd haring-harness && ./install.sh

## Use

**1. Launch Claude the way you normally do.**

**2. Mention haring in your prompt:**

    /haring <what you want done>

Example:

    /haring The app is crashing, find the reason and fix it.

## What haring writes into your project

    .haring/runs/{stamp}-{kind}-{pid}/
      prompt.md      what the worker was asked, the only copy of the question
      report.json    what it returned
      stats.txt      model, tokens, cache reads, turns, seconds
      meta           what the run was, so it can be continued
      PROGRESS.md    only for kinds that change files, written as they go
      stderr.txt     only when something went wrong

The first time haring writes a run into a repository it adds `.haring/` to that
repository's `.gitignore`. Nothing in there needs maintaining. It is a record, not a
document.

## Development and contributing

### Structure

    bin/            haring-worker    start a worker, or continue one
                    haring-wait      follow a run, then print its report
                    haring-pulse     one line per live worker, at a fixed interval
                    haring-report    print a report, with the empty parts removed
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
