"""Desktop body: a REPL at your keyboard.

Owns no memory, no persona and no rules — it opens the brain, forwards what you
typed to the shared handler, and prints the reply.

    python3 body_desktop.py --brain ../demo/brain
"""

from __future__ import annotations

import argparse
import sys

from brain import handle, open_brain

BODY = "desktop"


def repl(brain, stdin=sys.stdin, stdout=sys.stdout) -> None:
    while True:
        stdout.write("you> ")
        stdout.flush()
        line = stdin.readline()
        if not line or line.strip() in ("quit", "exit"):
            break
        if not line.strip():
            continue
        stdout.write(f"[{BODY}] {handle(brain, line, BODY)}\n")
        stdout.flush()
    stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--brain", help="path to the shared vault (or set BRAIN_PATH)")
    args = parser.parse_args(argv)
    repl(open_brain(args.brain))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
