# Walkthrough

Six minutes, no network, no credentials. You teach the desk body a fact, watch
the phone body not know it yet, sync, watch it know — then force a conflict and
watch newest-wins settle it in writing.

Run everything from the repo root. Each block is copy-paste; the output shown is
what you should see, minus timestamps and the temp path.

## Set up two bodies

The vault is one brain, but each body keeps its own copy on its own machine.
Here they are two folders in a scratch directory.

```bash
work=$(mktemp -d)
cp -R demo/brain "$work/desk-brain"
cp -R demo/brain "$work/phone-brain"
```

## 1. Teach the desk body

```bash
printf 'remember the launch review moved to Thursday\nquit\n' \
  | python3 skeleton/body_desktop.py --brain "$work/desk-brain"
```

```
you> [desktop] Remembered, in the brain: the launch review moved to Thursday
you>
```

The fact landed in `memory/learned.md` plus today's note in `daily/` — in the
brain, not in the body.

## 2. Ask the phone body, before the sync

```bash
python3 skeleton/body_bot.py --brain "$work/phone-brain" --messages demo/messages.txt
```

```
[phone -> demo-chat] Nothing in memory about that yet. Teach me with: remember <fact>
```

Correct, and the reason it is correct matters: the phone body is not a second
assistant with a worse memory. It is the same entity reading a copy of the brain
that is two minutes stale.

## 3. Sync — dry run first

```bash
skeleton/sync.sh "$work/desk-brain" "$work/phone-brain" --dry-run
```

```
would resolve: <timestamp> memory/learned.md — kept desk-brain (mtime …), overwrote phone-brain (mtime …)
sending incremental file list
daily/<today>.md
memory/learned.md
… (DRY RUN)
sending incremental file list
memory/learned.md
… (DRY RUN)
```

The first line is the decision; the rest is rsync listing what each leg would
copy. Nothing was written — the dry run moves no bytes and appends no log line.
Now for real:

```bash
skeleton/sync.sh "$work/desk-brain" "$work/phone-brain"
```

## 4. Ask the phone body again

```bash
python3 skeleton/body_bot.py --brain "$work/phone-brain" --messages demo/messages.txt
```

```
[phone -> demo-chat] daily/<today>.md: Learned through the desktop body: the launch review moved to Thursday | memory/learned.md: <today> — the launch review moved to Thursday (learned through the desktop body)
```

Two hits because the fact was written twice on purpose: to its owner note and to
today's receipt line.

Same question, same entity, other body. Nothing about the answer came from the
bot — the bot only carried the message.

## 5. Force a conflict

Both sides edit the same note before a sync runs. The phone edits second.

```bash
printf -- '- 2025-06-03 — desk says the review is at 10:00\n' >> "$work/desk-brain/memory/learned.md"
sleep 1
printf -- '- 2025-06-03 — phone says the review is at 11:00\n' >> "$work/phone-brain/memory/learned.md"
skeleton/sync.sh "$work/desk-brain" "$work/phone-brain"
tail -1 "$work/desk-brain/system/sync-log.md"
```

```
- <timestamp> memory/learned.md — kept phone-brain (mtime …), overwrote desk-brain (mtime …)
```

The phone's version is now on both sides and the desk's 10:00 line is gone. That
is the design working, not failing: newest wins per file, and the write it cost
you is named in the log rather than quietly disappearing. If you need both
edits, the log tells you exactly which file to go re-read in git history.
