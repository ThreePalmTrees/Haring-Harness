#!/bin/sh
# Link haring into place. Safe to run again as often as you like.
#
# Everything is linked, not copied, so editing a file in this repository takes
# effect at once. Run this again only when you add a new script to bin/, or when
# you move this repository somewhere else.
set -e
HARING=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

link() {  # link <target> <linkname>
  target=$1; name=$2
  if [ -L "$name" ]; then
    old=$(readlink "$name")
    if [ "$old" = "$target" ]; then printf '  same    %s\n' "$name"; return; fi
    ln -sfn "$target" "$name"; printf '  moved   %s\n            was %s\n' "$name" "$old"; return
  fi
  if [ -e "$name" ]; then
    printf '  SKIP    %s exists and is not a link. Move it aside, then run this again.\n' "$name" >&2
    failed=1; return
  fi
  ln -sfn "$target" "$name"; printf '  new     %s\n' "$name"
}

failed=0
echo "haring: $HARING"
echo
echo "skill:"
mkdir -p "$HOME/.claude/skills"
link "$HARING/skills/haring" "$HOME/.claude/skills/haring"

echo "claude code agent (the QA pass, on opus by default):"
mkdir -p "$HOME/.claude/agents"
link "$HARING/claude/agents/haring-qa.md" "$HOME/.claude/agents/haring-qa.md"

echo "opencode agents (one per kind of worker):"
mkdir -p "$HOME/.config/opencode/agents"
for f in "$HARING"/opencode/agents/haring-*.md; do
  link "$f" "$HOME/.config/opencode/agents/$(basename "$f")"
done

# The OpenCode service does not see an edit made through these links, so it is told to
# read its configuration again; without this an agent's changed rules do nothing.
if command -v opencode >/dev/null 2>&1; then
  opencode reload </dev/null >/dev/null 2>&1 && echo "  reloaded the OpenCode service's configuration" \
    || echo "  note    could not reach the OpenCode service to reload it; run: opencode reload"
fi

echo "scripts:"
mkdir -p "$HOME/.local/bin"
for f in "$HARING"/bin/*; do
  [ -f "$f" ] || continue
  link "$f" "$HOME/.local/bin/$(basename "$f")"
done

# Links in ~/.local/bin that no longer point at a file in this repository's bin/
for f in "$HOME"/.local/bin/haring-*; do
  [ -L "$f" ] || continue
  [ -e "$f" ] || { rm -f "$f"; printf '  removed %s (dangling)\n' "$f"; continue; }
  case "$(readlink "$f")" in
    "$HARING"/bin/*) : ;;
    *) printf '  note    %s points outside this repository\n' "$f" ;;
  esac
done

echo
case ":$PATH:" in
  *":$HOME/.local/bin:"*) : ;;
  *) echo "warning: $HOME/.local/bin is not on your PATH. Add it, or the manager cannot find haring-root." >&2 ;;
esac

if ! command -v opencode >/dev/null 2>&1; then
  echo "warning: opencode is not on your PATH. Workers run in OpenCode; install it, then" >&2
  echo "  sign in to OpenCode Go with: opencode auth login" >&2
fi

[ "$failed" = 0 ] || { echo "Nothing else to do until the lines marked SKIP are dealt with." >&2; exit 1; }

echo "Done. Run /haring inside any project."
echo
echo "Editing rules, schemas or reference files takes effect on the next worker you"
echo "start. Editing SKILL.md may need a fresh Claude Code session, because the skill"
echo "list is read when a session begins."
