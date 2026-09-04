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

if ! security find-generic-password -a "$USER" -s haring-zai >/dev/null 2>&1; then
  echo "The worker API key is not in the Keychain yet. Add it with:"
  echo "  security add-generic-password -a \"\$USER\" -s haring-zai -U -w"
  echo "Put -w last with no value so it prompts and the key stays out of your shell history."
  echo
fi

[ "$failed" = 0 ] || { echo "Nothing else to do until the lines marked SKIP are dealt with." >&2; exit 1; }

echo "Done. Run /haring inside any project."
echo
echo "Editing rules, schemas or reference files takes effect on the next worker you"
echo "start. Editing SKILL.md may need a fresh Claude Code session, because the skill"
echo "list is read when a session begins."
