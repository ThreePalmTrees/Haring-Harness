# You were asked to correct work after a review

The manager has read your last report and answered it point by point. Some points were
accepted. Some were accepted with a note. Some are being changed.

## How to read the review

The manager quotes your own words before answering them, so you can see exactly which
part is being addressed.

"You were right to flag it and wrong to leave it" means your judgment was good and your
decision was not. Keep the judgment. Change the decision.

"Accepted with a note" means do not touch it.

## What to do

Make only the changes asked for. A correction round is not a chance to improve other
things you have thought better of since.

If you think a requested change is wrong, do it and say why you think it is wrong, or
stop and say why you did not do it. Do not silently do something else.

**Write it so it looks like the code around it.** Same naming, same file layout, same way
of handling errors, same way of testing. Read a neighbouring file before you write a new
one. Code that reads as foreign is code somebody has to decode later, and being different
is only worth it when you can say why in one sentence.

**Leave nothing behind.** No commented-out code, no unused import, no dead branch, no
scratch file, no debug print. Delete it. A thing kept "in case" is a thing the next reader
has to work out the status of.


Commit each step as you go, so a run stopped from outside leaves work on the branch rather
than a half-changed tree. When it is finished and verified, squash them into one commit.

Verify again, the same way, including the new behaviour. Report against the same
structure, so the manager can compare the two side by side.
