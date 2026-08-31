#!/usr/bin/env bash
# Two-way vault sync: the spine that keeps two bodies one entity.
#
# Transport only. The newest-wins rule and the sync-log format live in brain.py
# so the shell never gets a second opinion about who won.
#
#   ./sync.sh <vault-a> <vault-b> [--dry-run]
#
# Run it on a short interval (cron, a timer, a loop) from ONE side; the log of
# resolutions is written into vault-a and rides the sync over to vault-b.

set -euo pipefail

usage() {
	echo "usage: $(basename "$0") <vault-a> <vault-b> [--dry-run]" >&2
	exit 2
}

[ $# -ge 2 ] || usage
vault_a=$1
vault_b=$2
shift 2

dry_run=""
for arg in "$@"; do
	case "$arg" in
	--dry-run) dry_run=1 ;;
	*) usage ;;
	esac
done

here=$(cd "$(dirname "$0")" && pwd)
python3 "$here/brain.py" resolve "$vault_a" "$vault_b" ${dry_run:+--dry-run}

# -u is the transport half of newest-wins: never overwrite a newer file, and
# skip on an exact tie. -a preserves mtimes, without which the second leg would
# see freshly copied files as the newer ones and bounce them straight back.
rsync_flags=(-a -u --exclude .git --exclude __pycache__ --exclude .DS_Store)
if [ -n "$dry_run" ]; then
	rsync_flags+=(-n -v)
fi

rsync "${rsync_flags[@]}" "${vault_a%/}/" "${vault_b%/}/"
rsync "${rsync_flags[@]}" "${vault_b%/}/" "${vault_a%/}/"
