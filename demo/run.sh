#!/usr/bin/env bash
# The README's quick start, verbatim, run in a scratch directory so nothing
# in your working copy gets touched. See the "By hand" block in README.md
# for the same nine lines spelled out.
set -euo pipefail

here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here"

work=$(mktemp -d)                       # two bodies, two copies of the brain
cp -R demo/brain "$work/desk-brain"
cp -R demo/brain "$work/phone-brain"

printf 'remember the launch review moved to Thursday\nquit\n' \
  | python3 -m phone_body.body_desktop --brain "$work/desk-brain"
phone_body/sync.sh "$work/desk-brain" "$work/phone-brain"
python3 -m phone_body.body_bot --brain "$work/phone-brain" --messages demo/messages.txt
