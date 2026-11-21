#!/bin/sh
# Unlink haring from this machine, the way install.sh linked it in.
#
#   ./uninstall.sh
#   ./uninstall.sh --worker <name>
#
# A link is removed only when its target is inside this repository — inside skills/ for
# the skill folder, which may hold more than one haring skill — so a plain file, and a
# link that points anywhere else, is left alone. A plain file named haring* in one of the
# folders install.sh writes to is listed at the end, to delete by hand. Nothing else is
# touched: no project's .haring/ folder or .gitignore is read or written.
#
# --worker runs only that worker's agents-config remove, so one worker's agent links go
# and every other link stays.
set -e
HARING=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

removed=0
leftover=0

usage() {
  echo "usage: uninstall.sh [--worker <name>]" >&2
  exit 2
}

# Remove one link when its target is inside the repository, or inside the folder given.
remove() {  # remove <linkname> [<target-folder>]
  name=$1
  prefix=${2:-$HARING}
  [ -L "$name" ] || return 0
  target=$(readlink "$name")
  case "$target" in
    "$prefix"/*) rm -f "$name"; printf '  removed %s\n' "$name"
                 removed=$((removed + 1)) ;;
    *) printf '  note    %s points somewhere else; left it\n' "$name" ;;
  esac
}

# Name every plain file called haring* left in a folder install.sh writes to.
leftovers() {  # leftovers <folder>
  for name in "$1"/haring*; do
    [ -f "$name" ] && [ ! -L "$name" ] || continue
    if [ "$leftover" = 0 ]; then
      echo
      echo "left over (plain files, not links):"
    fi
    printf '  left    %s\n' "$name"
    leftover=$((leftover + 1))
  done
}

worker_names() {
  for d in "$HARING"/workers/*; do
    [ -f "$d/agents-config" ] || continue
    basename "$d"
  done
}

if [ $# -gt 0 ]; then
  case "$1" in
    --worker)
      [ $# -eq 2 ] && [ -n "$2" ] || usage
      worker=$2
      found=""
      for name in $(worker_names); do
        if [ "$name" = "$worker" ]; then found=1; fi
      done
      [ -n "$found" ] || {
        echo "uninstall.sh: no worker named $worker. The workers here are:" >&2
        for name in $(worker_names); do echo "  $name" >&2; done
        exit 2; }
      exec "$HARING/workers/$worker/agents-config" remove
      ;;
    *) usage ;;
  esac
fi

failed=0
echo "haring: $HARING"
echo
echo "skill:"
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    ''|'#'*) continue ;;
    '~/'*) dir=$HOME/${line#'~/'} ;;
    *) dir=$line ;;
  esac
  printf '  %s\n' "$dir"
  for name in "$dir"/*; do remove "$name" "$HARING/skills"; done
  leftovers "$dir"
done < "$HARING/skill-dirs"

echo "worker agents:"
for w in "$HARING"/workers/*/agents-config; do
  [ -f "$w" ] || continue
  "$w" remove || failed=1
done

echo "scripts:"
for name in "$HOME"/.local/bin/haring-*; do remove "$name"; done

leftovers "$HOME/.claude/agents"
leftovers "$HOME/.local/bin"
leftovers "$HOME/.config/opencode/agents"

echo
[ "$failed" = 0 ] || { echo "Some worker links could not be removed." >&2; exit 1; }
if [ "$leftover" -gt 0 ]; then
  echo "$leftover plain file(s) named haring* were left alone; delete them by hand."
fi
echo "Done. Removed the links that pointed into $HARING."
