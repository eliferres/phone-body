# One brain, two bodies

An assistant you can reach at your desk and from your pocket is usually built as
two assistants: a desktop harness with its files, and a bot with its own prompt,
its own history and its own idea of who you are. They drift within a week. You
learn to ask the good one.

This is the other shape. One brain — a plain-file memory vault holding persona,
rules and everything the entity knows — and two thin bodies that do nothing but
carry messages to it. The phone body is not a smaller assistant. It is the same
assistant, reached through a different door.

```
                        ┌──────────────────────────────┐
                        │        THE BRAIN             │
                        │  a plain-file memory vault   │
                        │                              │
                        │  INDEX.md      the router    │
                        │  memory/       what it knows │
                        │  system/RULES  what binds it │
                        │  system/sync-log  who won    │
                        └──────────────────────────────┘
                             ▲                    ▲
              copy on disk   │                    │   copy on disk
                             │                    │
        ┌────────────────────┴───┐          ┌─────┴──────────────────┐
        │   DESKTOP BODY         │          │   PHONE BODY           │
        │   your machine         │          │   small always-on box  │
        │                        │          │                        │
        │   terminal / editor    │          │   long-polling bot     │
        │   local credentials    │          │   its own credential   │
        │   → handle()           │          │   → handle()           │
        └────────────────────────┘          └────────────────────────┘
                             ▲                    ▲
                             │                    │
                             └──── sync.sh ───────┘
                              two-way, short interval,
                              newest wins, every
                              resolution logged
```

Both bodies call one function, `handle()`, on their own copy of the brain. The
copies are held together by an interval sync. That is the whole architecture;
everything below is the reasoning that keeps it honest.

## Principle 1 — one brain

The brain is a folder of Markdown notes in the format of
[agent-memory-vault](https://github.com/eliferres/agent-memory-vault): a small
always-loaded router, one home per topic, newest wins, receipts in a daily note.
Persona, standing rules, decisions and learned facts all live there.

The rule that makes the entity singular is negative: **nothing durable may live
in a body.** No per-body prompt, no local cache of "what the user said", no
"phone personality". If the phone body needs to know that the user prefers short
answers, that preference is a line in `memory/user-preferences.md`, which the
desk body reads too. A body you delete and rebuild loses nothing.

A useful test when adding anything: if I deleted this body right now and stood
up a new one on a different machine, would the entity be less than it was? If
yes, what you just added belongs in the brain.

## Principle 2 — sync is the spine

Two copies of the brain exist because two machines exist. They are reconciled by
a two-way sync on a short interval — two minutes in practice, an interval you
should treat as part of the design, not an implementation detail.

The rule is **newest wins, per file, by modification time.** File granularity is
a deliberate trade: it is cheap, it needs no merge logic and no server, and it
loses the older of two concurrent edits to the same file. So every resolution is
appended to `system/sync-log.md` before any bytes move — winner, loser, both
timestamps. A lost write is not prevented; it is made visible, which is the
property you actually need when the alternative is silence.

Two details keep the loop stable:

- `rsync -a` preserves modification times. Without it, files copied on the first
  leg look freshly modified on the second and bounce straight back.
- `rsync -u` refuses to overwrite a newer file, and skips on an exact tie. The
  Python half applies the same tie rule, so the decision and the transport never
  disagree.

The sync log is itself a file inside the vault, which means it cannot be written
by both sides — it would conflict with itself every run. Only the side running
the sync appends to it; the log then rides the sync to the other body.

**Bodies must tolerate being stale.** A body that has not synced in three minutes
answers from three-minute-old memory, and that is a normal state, not an error.
It follows that a body must never treat its copy as authoritative for anything
irreversible: recent-write-sensitive actions (did I already send that? did I
already pay that?) belong behind a check against the thing itself, never against
memory that might be a sync behind.

## Principle 3 — bodies are disposable

A body holds exactly two things: its own credentials, and a path to the brain.
That is the entire contract. Standing up a new body — a second laptop, a bot on
a different network, a terminal on a borrowed machine — is configuration:

1. Give the machine a copy of the vault.
2. Point the sync at it.
3. Give the body its own credential, never a copy of another body's.

There is no step where you port logic. When the responder improves, it improves
in one place and every body gets it on the next pull, because every body calls
the same `handle()`.

Separate credentials per body matter for the failure case below: revoking one
body must not blind the others.

## Principle 4 — one set of rules

Guardrails belong to the entity, not to the machine you happened to use. A
spending limit the desk enforces and the phone does not is not a limit — it is a
speed bump with a documented bypass, and the bypass is the one that lives in your
pocket at 2am.

So the rules live in the brain (`system/RULES.md`), and each body's adapter
enforces them locally, before acting. Locally is the load-bearing word: there is
no shared enforcement server, so a rule is only as real as the weakest adapter.
When you add a body, porting the enforcement is the work — the rules themselves
you get for free.

The skeleton in this repo ships the rules file and the shared handler seam but
does not implement enforcement; a real deployment adds the checks inside
`handle()` (one place, both bodies) and refuses at the boundary.

## Failure modes

**Split brain.** Two bodies diverge and neither is wrong. Real causes: the sync
was down, a machine was offline, or two edits landed inside one interval. The
design answers with resolution, not prevention — newest wins settles it in
bounded time, and the sync log turns every silent loss into a line you can read.
What the design deliberately refuses is a merge algorithm: automatic merging of
prose memory produces notes that say two things, which is worse than losing the
older one visibly. Keep the vault in git and the loser is recoverable.

**Sync loops.** A file ping-pongs between bodies forever, each leg touching its
timestamp. Prevented by preserving mtimes (`-a`), refusing to overwrite newer
files (`-u`), and never letting both sides append to the same generated file —
which is why the sync log has exactly one writer. A body that rewrites a note on
every boot ("last seen at …") will reintroduce this; keep churn out of the vault
and put it in the body, where nothing is expected to survive.

**A body outliving its revoked credentials.** The phone body sits on a small
always-on box. If that box is lost, the credential on it is loose, and it has a
readable copy of everything the entity knows. Three answers, in order of how much
they buy: give every body its own credential so one revocation is surgical; keep
the brain's copy on that box encrypted at rest and treat revocation as a
credential rotation plus a wipe; and accept the honest limit — **a body has read
everything, so a lost body is a memory disclosure, not just a lost key.** If some
category of fact must never sit on the always-on box, it does not belong in the
synced vault at all. That is a decision to make before the first sync, not after
the box goes missing.
