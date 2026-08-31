# phone-body

Reach your assistant at your desk or from your pocket and get the same entity
either way — same memory, same rules, same answer. Not a desktop agent plus a
bot that half-knows you: one brain in a plain-file vault, two thin bodies that
carry messages to it, and a two-way sync that keeps them honest. This repo is
the architecture writeup plus a runnable skeleton you can drive offline in a
minute, no credentials and no server.

The memory format is [agent-memory-vault](https://github.com/eliferres/agent-memory-vault),
unchanged: a router note, one home per topic, newest wins.

![ci](https://github.com/eliferres/phone-body/actions/workflows/ci.yml/badge.svg)

## Quick start

```bash
git clone https://github.com/eliferres/phone-body.git
cd phone-body
work=$(mktemp -d)                       # two bodies, two copies of the brain
cp -R demo/brain "$work/desk-brain"
cp -R demo/brain "$work/phone-brain"

printf 'remember the launch review moved to Thursday\nquit\n' \
  | python3 skeleton/body_desktop.py --brain "$work/desk-brain"
skeleton/sync.sh "$work/desk-brain" "$work/phone-brain"
python3 skeleton/body_bot.py --brain "$work/phone-brain" --messages demo/messages.txt
```

The bot answers with what you told the desktop. Zero dependencies, Python 3.9+,
`rsync` and `bash` for the sync. The full tour — including forcing a conflict and
reading the resolution out of the sync log — is
[demo/WALKTHROUGH.md](demo/WALKTHROUGH.md).

## The four principles

**One brain.** Both bodies read and write the same vault. Persona, standing
rules, decisions and learned facts live there, never in a body's code. The test
for anything you are about to add: if I deleted this body and stood up a new one,
would the entity be less than it was? If yes, it belongs in the brain.

**Sync is the spine.** The vault syncs both ways on a short interval — minutes,
not hours. Conflicts resolve newest-wins per file, and every resolution is
written to a sync log, so a lost write is visible instead of silent. Bodies must
tolerate being minutes stale, which means memory is never the authority for
anything irreversible.

**Bodies are disposable.** A body holds two things: its own credentials, and a
path to the brain. Standing up a new one — second laptop, new bot, borrowed
terminal — is configuration, not surgery, because there is no logic to port.

**One set of rules.** Guardrails belong to the entity, not the machine. A
spending limit the desk enforces and the phone ignores is a bypass that lives in
your pocket. So the rules live in the brain and each body's adapter enforces
them locally.

The long version, with the ASCII diagram and the failure modes, is
[docs/architecture.md](docs/architecture.md).

## The sync contract, verbatim

Two rules and one receipt. This is the whole reconciliation model:

```
newest wins, per file, by modification time
  an exact tie changes nothing on either side and is flagged for a human
  the older concurrent edit to the same file is lost, by design, visibly

every resolution is appended to system/sync-log.md before any bytes move
  - <when> <file> — kept <winner> (mtime <t>), overwrote <loser> (mtime <t>)

the log has exactly one writer: the side running the sync
  it is a synced file, so two writers would conflict with itself every run
```

A real line, from step 5 of the walkthrough:

```
- 2026-08-31T01:11:31Z memory/learned.md — kept phone-brain (mtime 2026-08-31T01:11:31.402Z), overwrote desk-brain (mtime 2026-08-31T01:11:30.118Z)
```

And the contract a body signs, in full: hold your own credentials, hold a path
to the brain, hold nothing else.

## What is in the box

| Path | Role |
|---|---|
| `docs/architecture.md` | The writeup: diagram, four principles, failure modes. |
| `docs/wiring.md` | How to replace the offline transport with a real chat bot. |
| `skeleton/brain.py` | The vault: read, recall, remember, newest-wins, sync log. |
| `skeleton/body_desktop.py` | Desktop body — a REPL. Carries messages, owns nothing. |
| `skeleton/body_bot.py` | Phone body — the same loop, long-polling shaped, offline. |
| `skeleton/sync.sh` | Two-way rsync transport, `--dry-run` supported. |
| `demo/brain/` | A tiny vault in the memory format, fictional content. |
| `demo/WALKTHROUGH.md` | Teach one body, sync, ask the other, force a conflict. |
| `tests/test_brain.py` | Hermetic: temp vaults, real files, no network. |

Both bodies call one function, `handle()` in `brain.py`. That is the seam where
your model call goes, and putting it there is what keeps the two bodies one
entity: the reply depends on the brain, never on which body you reached.

## Why not just run two assistants

Because they diverge within a week, and you learn which one to ask. The moment
the phone has its own prompt or its own history, you own two entities with one
name, and every correction has to be made twice. The cost of one brain is that
you must accept staleness and a real conflict rule; the cost of two assistants is
that you never know which one is right.

Files rather than a database for the same reason the memory format uses them:
inspectable, diffable, syncable with tools that already exist on every machine,
and recoverable from git when newest-wins takes the write you wanted.

## Limitations

- Newest wins per file loses the older concurrent edit. That is the trade for
  needing no merge logic and no server; the sync log makes the loss visible, and
  git makes it recoverable, but nothing merges the two versions for you.
- Interval sync means a body can answer from memory that is minutes old. Fine
  for recall, wrong for anything irreversible — check the source of truth, not
  memory, before acting.
- The responder is a stub: it greps the vault. Bring your own model call; the
  skeleton exists to show where it plugs in and what it must not depend on.
- The bot transport is offline by design. Real hosting needs an allow-list,
  credential rotation, backoff and a supervisor, described in `docs/wiring.md`
  and not shipped here.
- Rules live in the brain, but enforcement is per-adapter and this skeleton
  ships none. A rule is only as strong as the weakest body you wired.
- A body has read everything. Losing the machine is a memory disclosure, not
  just a lost credential. Decide what may sync to an always-on box before the
  first sync, not after.

## License

MIT
