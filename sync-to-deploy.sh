#!/usr/bin/env bash
# Mirror this repo's tracked tree into the repo that actually deploys.
#
# WHY THIS EXISTS
#   Two repos, unrelated histories (no common ancestor, so `git merge` is impossible):
#     hackathon/sitemind/   -> github.com/AwkJay/sitemind                    (development, deploys nothing)
#     hackathon/sitemind2/  -> github.com/AwkJay/sitemind-openai-hackathon   (Vercel + Render build from THIS)
#   Vercel and Render were wired up back when this folder still pointed at the
#   openai-hackathon remote; its .git was later deleted and re-initialised, so the
#   platforms kept watching the original repo. Rather than repoint them (Render
#   would likely need new services => new *.onrender.com URLs), we mirror.
#   Full explanation: docs/deploy.md §3.
#
# WHAT IT DOES
#   Copies every git-tracked file from here into the deploy clone, refreshes any
#   file the deploy repo tracks that also exists here, commits normally (never a
#   force push, never a history rewrite) and pushes. That push is what triggers
#   the deploy.
#
# USAGE
#   ./sync-to-deploy.sh                 # sync + commit + push
#   ./sync-to-deploy.sh --dry-run       # show what would change, touch nothing
#   ./sync-to-deploy.sh -m "message"    # custom commit message
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST="${SITEMIND_DEPLOY_DIR:-$(dirname "$SRC")/sitemind2}"
DRY=0
MSG="Sync from main project"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    -m) MSG="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -d "$DST/.git" ]] || { echo "ERROR: deploy clone not found at $DST" >&2; exit 1; }

# Guard: make sure we're pointed at the right pair of remotes, not two copies of
# the same repo (which would silently no-op) or something unrelated.
src_remote="$(git -C "$SRC" remote get-url origin)"
dst_remote="$(git -C "$DST" remote get-url origin)"
[[ "$dst_remote" == *sitemind-openai-hackathon* ]] || {
  echo "ERROR: $DST does not point at the deploy repo (origin = $dst_remote)" >&2; exit 1; }
[[ "$src_remote" != "$dst_remote" ]] || {
  echo "ERROR: source and destination share a remote — nothing to mirror" >&2; exit 1; }

git -C "$SRC" diff --quiet && git -C "$SRC" diff --cached --quiet || {
  echo "ERROR: $SRC has uncommitted changes. Commit them first so the mirror" >&2
  echo "       matches a real commit on $src_remote." >&2; exit 1; }

echo "source : $SRC  ($src_remote @ $(git -C "$SRC" rev-parse --short HEAD))"
echo "deploy : $DST  ($dst_remote @ $(git -C "$DST" rev-parse --short HEAD))"
echo

# Files to copy: everything tracked here, PLUS anything the deploy repo tracks
# that also exists here. That second set matters because docs/ is gitignored in
# this repo but several docs files are tracked in the deploy repo — without it
# they would go stale (or get deleted) on every sync.
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
git -C "$SRC" ls-files > "$tmp/src"
git -C "$DST" ls-files > "$tmp/dst"
while read -r f; do [[ -f "$SRC/$f" ]] && echo "$f"; done < "$tmp/dst" >> "$tmp/src"
sort -u "$tmp/src" > "$tmp/files"

# Anything the deploy repo tracks that no longer exists here at all is a real
# deletion and must be propagated, or the deploy repo keeps building dead files.
comm -13 <(sort -u "$tmp/files") <(sort "$tmp/dst") > "$tmp/gone"

if [[ $DRY -eq 1 ]]; then
  echo "--- of $(wc -l < "$tmp/files") mirrored files, these differ ---"
  # -i itemizes; the leading '>' rows are the files rsync would actually write.
  rsync -rlptni --files-from="$tmp/files" "$SRC/" "$DST/" | grep -E '^[<>ch]' || echo "(none — trees already match)"
  echo "--- would delete ---"; cat "$tmp/gone"
  echo; echo "(dry run — nothing changed)"; exit 0
fi

rsync -rlpt --files-from="$tmp/files" "$SRC/" "$DST/"
if [[ -s "$tmp/gone" ]]; then
  # shellcheck disable=SC2046
  git -C "$DST" rm -q --ignore-unmatch $(cat "$tmp/gone")
fi

cd "$DST"
git add -A
if git diff --cached --quiet; then
  echo "Already in sync — nothing to commit."; exit 0
fi
git status --short
echo
git commit -q -m "$MSG"
git push origin main
echo
echo "Pushed $(git rev-parse --short HEAD) to $dst_remote"
echo "Vercel auto-deploys (~40s). Render may need a manual trigger — see docs/deploy.md §5."
