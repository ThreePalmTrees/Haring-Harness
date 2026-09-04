# Haring

A wrapper for using sub-agents, so you do not repeat the same setup every time.

Claude Opus 5 manages. GLM 5.3 Flash does the work. That pair is fixed: every rule here
was written for it and is only known to work in it. The manager never chooses a different
model; only the person who asked for the work can ask for one.

## Install

Haring lives in one place. Clone it wherever you keep your tools and run the installer
**once**, from inside this repository:

    ./install.sh
    security add-generic-password -a "$USER" -s haring-zai -U -w   # if not done yet

**Do not copy this repository into your projects.** The installer links the skill into
`~/.claude/skills/haring` and the scripts into `~/.local/bin`, both pointing back here.
After that, `/haring` works in every project on the machine, and updating haring means
pulling in this one directory.

Editing a rule or a schema takes effect on the next worker you start. Editing `SKILL.md`
needs a fresh Claude Code session. Run the installer again only when you add a script or
move this directory.

## Use

Inside any project:

    /haring <what you want done>

## The five kinds of task

    explore    find something out so the manager can plan
    implement  do the work, on a branch
    check      verify one claim, with no memory of having made it
    errand     a trivial mechanical job
    correct    apply what a review asked for

## What is here

    bin/            seven scripts: build a prompt, start a worker, wait for it,
                    read its report, read its numbers, read a session, find the repo
    skills/haring/  SKILL.md — everything the manager needs, in one file
    rules/          worker.md, and one file per kind of task
    schemas/        one report schema per kind

Every command that acts on a run takes the run folder, and only the run folder. All
of them exit 2 when they were called wrongly — a missing argument, an unknown kind, a
path that is not a haring run folder — and 1 when they were called rightly but could
not do the job. `haring-wait` has two exits beyond those: 3 when the worker has gone
and left no report.

`haring-worker` names each worker's session itself and writes the id in the run's meta,
so `haring-session` can tell a worker's transcript from the manager's before the worker
has done anything. It reads the manager's numbers, `-n N` asks for an older session,
and `-l` lists them.

## What haring writes into your project

    .haring/runs/<stamp>-<kind>-<pid>/
      prompt.md      what the worker was asked, the only copy of the question
      report.json    what it returned
      stats.txt      model, tokens, cache reads, turns, seconds
      meta           what it was, so the run can be continued
      PROGRESS.md    for kinds that change things, written as they go
      stderr.txt     only when something real went wrong

Nothing there needs maintaining. It is a record, not a document.

## Design

The full design, the findings behind every rule, and what is still open:
https://claude.ai/code/artifact/fa42c2be-cb3a-4ab4-9dfe-72c4f30a4169
