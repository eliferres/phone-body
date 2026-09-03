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

    def test_sync_sh_actually_overwrites_the_loser_on_disk(self):
        # NewestWins above only exercises brain_module.resolve() in-process
        # (dry_run=True, no rsync). This runs the real sync.sh end to end and
        # checks the transport half: the older file's bytes on disk, not just
        # the sync-log line, end up matching the winner.
        self.touch(self.desk_root, "memory/learned.md", "desk wins\n", mtime=2_000_000)
        self.touch(self.phone_root, "memory/learned.md", "phone loses\n", mtime=1_000_000)
        self.sync()
        self.assertEqual("desk wins\n", (self.phone_root / "memory/learned.md").read_text())
        self.assertEqual("desk wins\n", (self.desk_root / "memory/learned.md").read_text())

    def test_a_file_deleted_on_one_side_drifts_back(self):
        # sync.sh's rsync flags carry no --delete (see the comment above
        # rsync_flags in sync.sh), so a locally removed note is not a
        # propagated deletion - the other side's copy repopulates it. That is
        # drift, not a bug, but it must stay true on purpose, not by accident.
        (self.phone_root / "memory/learned.md").unlink()
        self.sync()
        self.assertTrue((self.phone_root / "memory/learned.md").exists())


class SyncScriptUsage(VaultCase):
    def test_missing_arguments_exits_2(self):
        result = subprocess.run(
            [str(SKELETON / "sync.sh"), str(self.desk_root)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("usage", result.stderr)

    def test_unknown_flag_exits_2(self):
        result = subprocess.run(
            [str(SKELETON / "sync.sh"), str(self.desk_root), str(self.phone_root), "--bogus"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("usage", result.stderr)


class BotMessageHandling(VaultCase):
    def test_bot_replies_to_every_message_in_one_batch(self):
        transport = body_bot.OfflineTransport(["remember x is 1", "remember y is 2"])
        sent = []
        transport.send = lambda chat, text: sent.append(text)
        body_bot.serve(self.desk, transport)
        self.assertEqual(2, len(sent))
        self.assertIn("Remembered", sent[0])
        self.assertIn("Remembered", sent[1])

    def test_bot_reads_messages_from_stdin_when_no_file_given(self):
        # --messages is optional (body_bot.py falls back to sys.stdin.read());
        # every other test in this file goes through --messages, leaving that
        # branch unexercised.
        result = subprocess.run(
            [sys.executable, str(SKELETON / "body_bot.py"), "--brain", str(self.desk_root)],
            input="remember stdin works too\n",
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Remembered", result.stdout)

    def test_bot_ignores_blank_lines_in_the_message_file(self):
        raw = "remember blank lines are skipped\n\n   \nquit is not special here\n"
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write(raw)
            path = fh.name
        self.addCleanup(os.unlink, path)
        result = subprocess.run(
            [sys.executable, str(SKELETON / "body_bot.py"), "--brain", str(self.desk_root), "--messages", path],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, result.stdout.count("[phone ->"))


if __name__ == "__main__":
    unittest.main()
