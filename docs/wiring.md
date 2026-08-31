# Wiring a real phone body

The skeleton's phone body talks to `OfflineTransport`, so it runs with no
network and no credential. This page is the instructions for replacing that one
class with a real chat client. It is deliberately prose, not code: a copy-paste
bot that ships with a credential slot is how credentials end up in git history.

Everything here assumes the architecture in [architecture.md](architecture.md).
The transport is the only piece that changes.

## The transport contract

Whatever chat platform you use, the adapter has to provide exactly two methods:

- `get_updates()` — returns a list of inbound messages, each a dict with a
  `chat` key (where to reply) and a `text` key (what was said). It should block
  until the platform has something or the poll times out, and return an empty
  list on timeout.
- `send(chat, text)` — posts one reply to that chat.

Write it as a class with those two methods, hand it to `serve()` with
`stop_when_idle=False`, and the body is done. Nothing else in the skeleton knows
what platform you are on.

## Steps

1. **Create the bot on your platform** and get its credential. Read the
   platform's own docs for this; every one of them differs and all of them
   change.

2. **Put the credential in the environment, never in a file in the repo.** The
   body reads it with `os.environ["..."]` at startup and fails loudly if it is
   missing — a body that starts without its credential and silently answers
   nobody is the worst of both worlds. Systemd's `EnvironmentFile=` with mode
   0600, or your host's secret store, is the right home for it.

3. **Lock the bot to you.** This is the step people skip. A public bot will be
   found, and a bot wired to your brain answers whoever finds it. Keep an
   allow-list of chat ids in the environment (not in the vault — allow-lists are
   body configuration), check it in `get_updates()`, and drop everything else
   without replying. Log the drops.

4. **Choose long-polling or webhooks.** Long-polling needs no inbound port and no
   certificate, which is why the skeleton is shaped that way; it costs you an
   idle connection. Webhooks need a public HTTPS endpoint, a certificate and a
   shared secret you verify on every request. Start with long-polling.

5. **Handle the network like a network.** Timeouts on every call, retry with
   backoff on 5xx and connection errors, and never let a failed `send()` take
   down the loop — the body should keep polling. Chat APIs rate-limit; respect
   the platform's backoff header rather than inventing one.

6. **Reply to the chat the message came from**, using the `chat` value from the
   update. Never a chat id you stored earlier: that is how a reply meant for you
   reaches someone else after an account change.

7. **Run it under a supervisor** (systemd, or whatever your host gives you) with
   restart-on-failure, and put the sync on its own short-interval timer next to
   it. The body dying is routine; the sync stopping is the failure that matters,
   because it is invisible — the entity just quietly gets stale. Alert on sync
   age, not on body uptime.

## Before you point it at your real brain

- **Message length.** Chat platforms cap messages. Truncate or split in the
  transport, not in `handle()` — the entity's answer should not change shape
  because of which body asked.
- **Ordering.** Long-polling can deliver a batch; process it in order and
  acknowledge only what you handled, or a crash mid-batch loses messages.
- **The box has everything.** The vault on that machine is a full copy of the
  brain. Encrypt it at rest, and decide up front which categories of fact are
  allowed to sync there at all.
- **Enforce the rules locally.** `system/RULES.md` binds this body exactly as it
  binds the desk. The checks go inside `handle()`, where both bodies run them.
