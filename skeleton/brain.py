"""The shared brain: one plain-file memory vault, read and written by every body.

Bodies are disposable, so nothing durable may live in one. Persona, rules and
memory all live here, in the vault format of
https://github.com/eliferres/agent-memory-vault. This module is the only place
that knows how to read it, how to write back, and how a conflict is decided.

Library first; it also exposes one command used by sync.sh:

    python3 brain.py resolve <vault-a> <vault-b> [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

LEARNED_NOTE = "memory/learned.md"
SYNC_LOG = "system/sync-log.md"
DAILY_DIR = "daily"

# Machine litter that must never travel between bodies or count as memory.
SKIP_NAMES = {".git", "__pycache__", ".DS_Store"}


# Dropped before matching, so "when is the launch review" finds the line about
# the launch review. A real responder is a model call; this is a floor.
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "when", "what",
    "where", "who", "whom", "how", "why", "did", "do", "does", "my", "me", "i",
    "you", "to", "of", "in", "on", "at", "for", "it", "its", "that", "this",
    "and", "or", "about", "with",
}


def now_stamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------- the vault


class Brain:
    """One vault on disk. Every body holds one of these and nothing else."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        if not (self.root / "INDEX.md").is_file():
            raise FileNotFoundError(
                f"Expected a brain vault with an INDEX.md at its root, got `{self.root}`"
            )

    @property
    def name(self) -> str:
        return self.root.name

    def read(self, relpath: str) -> str:
        return (self.root / relpath).read_text(encoding="utf-8")

    def notes(self) -> list[Path]:
        return sorted(
            p
            for p in self.root.rglob("*.md")
            if not SKIP_NAMES.intersection(p.relative_to(self.root).parts)
        )

    def recall(self, question: str) -> list[tuple[str, str]]:
        """Every meaningful word of the question must appear in the line. Crude on
        purpose: retrieval quality is the model's job, not the skeleton's."""
        words = [
            w.strip(".,?!:;\"'")
            for w in question.lower().split()
            if w.strip(".,?!:;\"'") not in STOPWORDS and len(w.strip(".,?!:;\"'")) > 1
        ]
        if not words:
            return []
        hits = []
        for note in self.notes():
            rel = note.relative_to(self.root).as_posix()
            if rel == SYNC_LOG:
                continue
            for line in note.read_text(encoding="utf-8").splitlines():
                stripped = line.strip("- ").strip()
                if stripped and all(w in line.lower() for w in words):
                    hits.append((rel, stripped))
        return hits

    def remember(self, fact: str, body: str) -> None:
        """A durable fact goes to its owner note plus today's receipt line, in the
        brain — never into the body that happened to hear it."""
        self._append(
            LEARNED_NOTE,
            f"- {today()} — {fact} (learned through the {body} body)",
            header="# Learned\n\nFacts the entity picked up while working, newest last.\n",
        )
        self._append(
            f"{DAILY_DIR}/{today()}.md",
            f"- Learned through the {body} body: {fact}",
            header=f"# {today()}\n\nOne line per durable thing that happened today.\n",
        )

    def append_sync_log(self, line: str) -> None:
        self._append(
            SYNC_LOG,
            line,
            header="# Sync log\n\nEvery conflict the sync resolved, so a lost write is visible.\n",
        )

    def _append(self, relpath: str, line: str, header: str) -> None:
        path = self.root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(header, encoding="utf-8")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")


def open_brain(option: str | None) -> Brain:
    """A body is told exactly one thing about the world: where the brain is."""
    path = option or os.environ.get("BRAIN_PATH")
    if not path:
        sys.stderr.write(
            "This body has no brain: pass --brain <vault path> or set BRAIN_PATH.\n"
        )
        raise SystemExit(2)
    return Brain(path)


# ------------------------------------------------------------- the responder


def answer(brain: Brain, question: str) -> str:
    """Stub responder: retrieval, no model call. Swap this one function for your
    model and both bodies get the upgrade at once."""
    hits = brain.recall(question)
    if not hits:
        return "Nothing in memory about that yet. Teach me with: remember <fact>"
    return " | ".join(f"{rel}: {line}" for rel, line in hits[:3])


def handle(brain: Brain, text: str, body: str) -> str:
    """Both bodies run this exact function, which is what makes them one entity:
    the reply depends on the brain, never on which body you reached."""
    text = text.strip()
    if text.startswith("remember "):
        fact = text[len("remember ") :].strip()
        if not fact:
            return "Nothing to remember: use `remember <fact>`."
        brain.remember(fact, body)
        return f"Remembered, in the brain: {fact}"
    return answer(brain, text)


# ------------------------------------------------------------ newest-wins


def source_wins(source: Path, dest: Path) -> bool:
    """Newest wins, by modification time. An exact tie leaves the destination
    alone, which is what `rsync -u` does, so both halves of the sync agree."""
    return source.stat().st_mtime > dest.stat().st_mtime


def _relative_notes(root: Path) -> set[str]:
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and not SKIP_NAMES.intersection(p.relative_to(root).parts)
    }


def resolve(vault_a: Brain, vault_b: Brain, dry_run: bool = False) -> list[str]:
    """Record how every divergent file will be resolved, before rsync moves bytes.

    Lines land in vault_a's sync log only: the log is a synced file, and a body
    that appended to its own copy would collide with itself on the next run.
    """
    lines = []
    for rel in sorted(_relative_notes(vault_a.root) & _relative_notes(vault_b.root)):
        if rel == SYNC_LOG:
            continue
        left, right = vault_a.root / rel, vault_b.root / rel
        if left.read_bytes() == right.read_bytes():
            continue
        if source_wins(left, right):
            winner, loser = (vault_a, left), (vault_b, right)
        elif source_wins(right, left):
            winner, loser = (vault_b, right), (vault_a, left)
        else:
            lines.append(
                f"- {now_stamp()} {rel} — same timestamp on both sides, kept both; resolve by hand"
            )
            continue
        lines.append(
            f"- {now_stamp()} {rel} — kept {winner[0].name} (mtime {_stamp(winner[1])}), "
            f"overwrote {loser[0].name} (mtime {_stamp(loser[1])})"
        )
    if lines and not dry_run:
        for line in lines:
            vault_a.append_sync_log(line)
    return lines


def _stamp(path: Path) -> str:
    """Milliseconds included: two edits a second apart are common, and a log that
    prints both sides with the same timestamp is a log nobody trusts."""
    moment = datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    resolver = sub.add_parser("resolve", help="log how divergent files will be resolved")
    resolver.add_argument("vault_a")
    resolver.add_argument("vault_b")
    resolver.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = parser.parse_args(argv)

    lines = resolve(Brain(args.vault_a), Brain(args.vault_b), dry_run=args.dry_run)
    prefix = "would resolve" if args.dry_run else "resolved"
    for line in lines:
        print(f"{prefix}: {line.lstrip('- ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
