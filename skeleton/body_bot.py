"""Phone body: the same loop, shaped as a long-polling chat bot.

Identical to the desktop body everywhere it matters — it calls the same handler
on the same brain. The only difference is the transport, and the transport here
is offline, so the demo needs no server, no credential and no network:

    python3 body_bot.py --brain ../demo/brain --messages ../demo/messages.txt

docs/wiring.md describes how to replace OfflineTransport with a real chat API.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from brain import handle, open_brain

BODY = "phone"


class OfflineTransport:
    """Stands in for a chat API. A real transport implements these two methods
    against the network: get_updates() long-polls for inbound messages,
    send() posts a reply back to the chat it came from."""

    def __init__(self, messages: list[str], chat: str = "demo-chat"):
        self._pending = [{"chat": chat, "text": text} for text in messages]

    def get_updates(self) -> list[dict]:
        """Returns the scripted batch once, then nothing — where a real client
        would block until the server has something or the poll times out."""
        pending, self._pending = self._pending, []
        return pending

    def send(self, chat: str, text: str) -> None:
        print(f"[{BODY} -> {chat}] {text}")


def serve(brain, transport, stop_when_idle: bool = True) -> None:
    while True:
        updates = transport.get_updates()
        if not updates:
            if stop_when_idle:
                return
            continue
        for update in updates:
            transport.send(update["chat"], handle(brain, update["text"], BODY))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--brain", help="path to the shared vault (or set BRAIN_PATH)")
    parser.add_argument(
        "--messages",
        help="file of inbound messages, one per line; omit to read stdin",
    )
    args = parser.parse_args(argv)

    raw = Path(args.messages).read_text(encoding="utf-8") if args.messages else sys.stdin.read()
    messages = [line.strip() for line in raw.splitlines() if line.strip()]
    serve(open_brain(args.brain), OfflineTransport(messages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
