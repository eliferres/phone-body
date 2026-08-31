"""Hermetic tests: temp vaults, real files, no network and no mocks.

Every case is one claim the README or the architecture doc makes out loud.
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKELETON = REPO / "skeleton"
sys.path.insert(0, str(SKELETON))

import brain as brain_module  # noqa: E402  (needs the path above)
import body_bot  # noqa: E402
import body_desktop  # noqa: E402


class VaultCase(unittest.TestCase):
    """Two copies of the shipped demo vault, the way two bodies hold them."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        self.desk_root = self.work / "desk-brain"
        self.phone_root = self.work / "phone-brain"
        shutil.copytree(REPO / "demo" / "brain", self.desk_root)
        shutil.copytree(REPO / "demo" / "brain", self.phone_root)
        self.desk = brain_module.Brain(self.desk_root)
        self.phone = brain_module.Brain(self.phone_root)

    def touch(self, root, relpath, text, mtime=None):
        path = root / relpath
        path.write_text(text, encoding="utf-8")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def sync(self, *extra):
        return subprocess.run(
            [str(SKELETON / "sync.sh"), str(self.desk_root), str(self.phone_root), *extra],
            capture_output=True,
            text=True,
            check=True,
        )


class NewestWins(VaultCase):
    def test_newer_desk_file_wins(self):
        self.touch(self.desk_root, "memory/learned.md", "desk\n", mtime=2_000_000)
        self.touch(self.phone_root, "memory/learned.md", "phone\n", mtime=1_000_000)
        lines = brain_module.resolve(self.desk, self.phone, dry_run=True)
        self.assertIn("kept desk-brain", "\n".join(lines))

    def test_newer_phone_file_wins(self):
        self.touch(self.desk_root, "memory/learned.md", "desk\n", mtime=1_000_000)
        self.touch(self.phone_root, "memory/learned.md", "phone\n", mtime=2_000_000)
        lines = brain_module.resolve(self.desk, self.phone, dry_run=True)
        self.assertIn("kept phone-brain", "\n".join(lines))

    def test_identical_timestamps_are_flagged_for_a_human(self):
        self.touch(self.desk_root, "memory/learned.md", "desk\n", mtime=1_500_000)
        self.touch(self.phone_root, "memory/learned.md", "phone\n", mtime=1_500_000)
        lines = brain_module.resolve(self.desk, self.phone, dry_run=True)
        self.assertIn("resolve by hand", "\n".join(lines))

    def test_conflict_writes_one_sync_log_line(self):
        self.touch(self.desk_root, "memory/learned.md", "desk\n", mtime=2_000_000)
        self.touch(self.phone_root, "memory/learned.md", "phone\n", mtime=1_000_000)
        brain_module.resolve(self.desk, self.phone)
        log = self.desk.read(brain_module.SYNC_LOG)
        self.assertEqual(1, log.count("memory/learned.md"))
        self.assertIn("overwrote phone-brain", log)

    def test_matching_files_are_not_reported_as_conflicts(self):
        self.assertEqual([], brain_module.resolve(self.desk, self.phone, dry_run=True))


class BodyStartup(VaultCase):
    def test_a_body_refuses_to_start_without_a_brain_path(self):
        env = {k: v for k, v in os.environ.items() if k != "BRAIN_PATH"}
        result = subprocess.run(
            [sys.executable, str(SKELETON / "body_desktop.py")],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("no brain", result.stderr)

    def test_a_folder_without_an_index_is_not_a_brain(self):
        with self.assertRaises(FileNotFoundError):
            brain_module.Brain(self.work)


class SharedMemory(VaultCase):
    def test_desktop_body_writes_the_fact_into_the_brain(self):
        stdin = io.StringIO("remember the review moved to Thursday\nquit\n")
        body_desktop.repl(self.desk, stdin=stdin, stdout=io.StringIO())
        self.assertIn("review moved to Thursday", self.desk.read(brain_module.LEARNED_NOTE))
        today = brain_module.today()
        self.assertIn("review moved to Thursday", self.desk.read(f"daily/{today}.md"))

    def test_bot_answers_from_what_the_other_body_learned(self):
        body_desktop.repl(
            self.desk, stdin=io.StringIO("remember the review moved to Thursday\n"), stdout=io.StringIO()
        )
        self.sync()
        transport = body_bot.OfflineTransport(["when is the review"])
        sent = []
        transport.send = lambda chat, text: sent.append(text)
        body_bot.serve(brain_module.Brain(self.phone_root), transport)
        self.assertEqual(1, len(sent))
        self.assertIn("moved to Thursday", sent[0])

    def test_an_unknown_question_says_so(self):
        self.assertIn("Nothing in memory", brain_module.handle(self.phone, "what is my hat size", "phone"))


class Sync(VaultCase):
    def test_dry_run_changes_nothing(self):
        self.touch(self.desk_root, "memory/learned.md", "desk only\n")
        before = {
            p.relative_to(self.phone_root).as_posix(): p.read_bytes()
            for p in self.phone_root.rglob("*")
            if p.is_file()
        }
        log_before = self.desk.read(brain_module.SYNC_LOG)
        self.sync("--dry-run")
        after = {
            p.relative_to(self.phone_root).as_posix(): p.read_bytes()
            for p in self.phone_root.rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)
        self.assertEqual(log_before, self.desk.read(brain_module.SYNC_LOG))

    def test_sync_carries_a_new_note_both_ways(self):
        self.touch(self.desk_root, "memory/from-desk.md", "desk note\n")
        self.touch(self.phone_root, "memory/from-phone.md", "phone note\n")
        self.sync()
        self.assertEqual("desk note\n", self.phone.read("memory/from-desk.md"))
        self.assertEqual("phone note\n", self.desk.read("memory/from-phone.md"))

    def test_second_sync_of_untouched_vaults_resolves_nothing(self):
        self.touch(self.desk_root, "memory/learned.md", "desk\n")
        self.sync()
        result = self.sync()
        self.assertEqual("", result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
