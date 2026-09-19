#!/usr/bin/env bash
# Flatten the repository to a single commit.
#
# Pruning frees space on the published site, but git keeps every photo ever
# committed, so .git grows forever. This throws that history away and starts
# again from the current files. Run it once a year, or when `du -sh .git`
# gets uncomfortable.
#
# It rewrites published history: any clone you have elsewhere must be deleted
# and cloned again. There is no undo.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "current .git size: $(du -sh .git | cut -f1)"
read -rp 'Flatten history to one commit and force-push? [y/N] ' reply
[[ ${reply:-n} =~ ^[Yy]$ ]] || { echo "cancelled"; exit 0; }

branch=$(git rev-parse --abbrev-ref HEAD)
git checkout -q --orphan _flat
git add -A
git commit -qm "Site contents as of $(date -u +'%Y-%m-%d')"
git branch -qD "$branch"
git branch -qm "$branch"
git push -f origin "$branch"
git reflog expire --expire=now --all
git gc --prune=now --aggressive -q
echo "done. .git is now $(du -sh .git | cut -f1)"
