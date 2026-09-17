"""The demo receipt: demo/transcript.json must be what the commands really print.

Every entry is replayed with bash in a scratch copy of the repo, starting with
the three setup lines of the README's By hand block, so the receipt needs no
setup hidden in this file. Only machine paths and wall-clock times are
normalized before comparing; everything else must match exactly.

Regenerate the transcript from a real run (never by hand):

    UPDATE_DEMO_TRANSCRIPT=1 python3 -m unittest tests.test_demo_transcript

The picture beside it, demo/terminal.svg, is drawn from the same transcript by
a renderer this repo does not ship: if a regenerated transcript changes what
the session shows, a maintainer redraws the picture.
"""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRANSCRIPT = REPO / "demo" / "transcript.json"
PICTURE = REPO / "demo" / "terminal.svg"
CHECKOUT_PLACEHOLDER = "/path/to/checkout"
WORK_PLACEHOLDER = "/path/to/work"
MARKER = "__entry__"  # ends each entry in the one bash session the replay runs

# Every pattern is anchored to the one place a volatile value appears, so a
# changed word, file name or winner around it still fails the comparison.

# Clock times cannot be predicted, so they go on both sides of a comparison.
CLOCK = [
    (re.compile(r"^(resolved: \d{4}-\d\d-\d\d)T\d\d:\d\d:\d\dZ ", re.MULTILINE), r"\1T<time>Z "),
    (re.compile(r"\(mtime \d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z\)"), "(mtime <mtime>)"),
]

# Dates, on the other hand, are checked: today's date is substituted into the
# transcript and the real output has to carry it.
DATED = [
    re.compile(r"^resolved: (\d{4}-\d\d-\d\d)T", re.MULTILINE),
    re.compile(r"\bdaily/(\d{4}-\d\d-\d\d)\.md: "),
    re.compile(r"memory/learned\.md: (\d{4}-\d\d-\d\d) \u2014 "),
]

# Rows of the picture: long commands wrap at this width into " \"-ended chunks.
PICTURE_CMD_WIDTH = 58
ELLIPSIS = "…"
SVG_NS = "{http://www.w3.org/2000/svg}"


def without_clock(text):
    for pattern, replacement in CLOCK:
        text = pattern.sub(replacement, text)
    return text


def with_todays_dates(text, today=None):
    """The transcript was captured on the day it was regenerated; the brain
    writes the date of the run. So the expected text moves to today, and a date
    the brain got wrong (a frozen clock, a stale note name) still fails."""
    today = today or datetime.date.today().isoformat()
    for pattern in DATED:
        text = pattern.sub(lambda m: m.group(0).replace(m.group(1), today), text)
    return text


def without_dates(text):
    """For comparing two stored artifacts, the transcript and the picture drawn
    from it, where neither side can be moved to today."""
    for pattern in DATED:
        text = pattern.sub(lambda m: m.group(0).replace(m.group(1), "<date>"), text)
    return text


def without_paths(text, pairs):
    for real, placeholder in pairs:
        text = text.replace(real, placeholder)
    return text


def replay(entries):
    """Run the session once, as one bash session in a scratch copy of the repo,
    and split the output back into one (out, status) pair per entry.

    One session, not one process per entry, because the transcript starts by
    making a scratch directory and the later entries use it: the shell state a
    reader carries from line to line has to survive here too.
    """
    scratch = Path(tempfile.mkdtemp())
    work = None
    try:
        checkout = scratch / "checkout"
        shutil.copytree(
            REPO,
            checkout,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "build", "*.egg-info"),
        )
        script = []
        for entry in entries:
            script.append(entry["cmd"])
            # The leading newline is what the split below consumes, so an
            # entry whose output has no final newline is still captured whole.
            script.append(f'printf \'\\n{MARKER} %s\\n\' "$?"')
        script.append(f'printf \'{MARKER} work %s\\n\' "$work"')
        (scratch / "session.sh").write_text("\n".join(script) + "\n", encoding="utf-8")

        env = dict(os.environ)
        env.pop("BRAIN_PATH", None)
        # The transcript says python3; make that the interpreter running the suite.
        env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), env.get("PATH", "")])
        session = subprocess.run(
            ["bash", str(scratch / "session.sh")],
            cwd=checkout,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # A marker line ends every entry, and one last line names the scratch
        # directory the session made, so its path can be given a stable name.
        chunks = session.stdout.split(f"\n{MARKER} ")
        if len(chunks) != len(entries) + 2:
            raise AssertionError(
                f"expected {len(entries) + 1} markers, got {len(chunks) - 1}; "
                f"session output:\n{session.stdout}"
            )
        work = chunks[-1].split("work ", 1)[1].strip()

        # Longest first, so the checkout path is not half-replaced by a prefix.
        pairs = sorted(
            {
                (str(checkout), CHECKOUT_PLACEHOLDER),
                (str(checkout.resolve()), CHECKOUT_PLACEHOLDER),
                (work, WORK_PLACEHOLDER),
                (str(Path(work).resolve()), WORK_PLACEHOLDER),
            },
            key=lambda pair: -len(pair[0]),
        )
        results = []
        out = chunks[0]
        for chunk in chunks[1:-1]:
            status, _, out_next = chunk.partition("\n")
            results.append((without_paths(out, pairs), int(status)))
            out = out_next
        return results
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        if work and Path(work).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
            shutil.rmtree(work, ignore_errors=True)


def wrapped_command_rows(cmd, width=PICTURE_CMD_WIDTH):
    if len(cmd) <= width:
        return [cmd]
    rows, current = [], ""
    for word in cmd.split(" "):
        candidate = (current + " " + word).strip()
        if len(candidate) > width and current:
            rows.append(current + " \\")
            current = word
        else:
            current = candidate
    if current:
        rows.append(current)
    return rows


def picture_rows(svg_path):
    """Text rows under the title bar; the title bar label carries its own font size."""
    rows = []
    for text in ET.parse(svg_path).getroot().iter(SVG_NS + "text"):
        if text.get("font-size"):
            continue
        spans = text.findall(SVG_NS + "tspan")
        if spans:
            rows.append(spans[-1].text or "")
        else:
            raw = text.text or ""
            rows.append(raw[4:] if text.get("class") == "cmd" and raw.startswith("    ") else raw)
    return rows


class DemoTranscript(unittest.TestCase):
    def setUp(self):
        self.entries = json.loads(TRANSCRIPT.read_text(encoding="utf-8"))

    def test_every_entry_matches_a_real_run(self):
        results = replay(self.entries)
        if os.environ.get("UPDATE_DEMO_TRANSCRIPT") == "1":
            for entry, (out, status) in zip(self.entries, results):
                entry["out"], entry["status"] = out, status
            TRANSCRIPT.write_text(
                json.dumps(self.entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        for number, (entry, (out, status)) in enumerate(zip(self.entries, results), start=1):
            with self.subTest(entry=number, cmd=entry["cmd"]):
                self.assertEqual(
                    without_clock(with_todays_dates(entry["out"])),
                    without_clock(out),
                    f"entry {number} output: expected (transcript) first, actual second",
                )
                self.assertEqual(entry["status"], status, f"entry {number} exit status")

    def test_a_date_the_brain_got_wrong_still_fails(self):
        stored = "[phone -> demo-chat] daily/2026-09-03.md: Learned through the desktop body: x"
        today = datetime.date.today().isoformat()
        expected = without_clock(with_todays_dates(stored))
        self.assertEqual(expected, without_clock(stored.replace("2026-09-03", today)))
        self.assertNotEqual(expected, without_clock(stored.replace("2026-09-03", "1999-12-31")))

    def test_transcript_holds_no_machine_paths(self):
        for entry in self.entries:
            for field in ("cmd", "out"):
                self.assertNotRegex(entry[field], r"/Users/|/private/var|/var/folders|/tmp/tmp")

    def test_every_picture_row_comes_from_the_transcript(self):
        # Both sides lose their timestamps first: a regenerated transcript
        # carries the new run's clock, and the picture still carries the clock
        # of the run it was drawn from.
        out_lines = [
            without_dates(without_clock(line))
            for entry in self.entries
            for line in entry["out"].splitlines()
        ]
        cmd_rows = [row for entry in self.entries for row in wrapped_command_rows(entry["cmd"])]
        rows = picture_rows(PICTURE)
        self.assertTrue(rows, "the picture has no text rows")
        for row in rows:
            shown = row[: -len(ELLIPSIS)] if row.endswith(ELLIPSIS) else row
            shown = without_dates(without_clock(shown))
            with self.subTest(row=row):
                self.assertTrue(
                    any(line.startswith(shown) for line in out_lines + cmd_rows),
                    f"picture row {row!r} traces to nothing in demo/transcript.json. "
                    "demo/terminal.svg is drawn from the transcript by a renderer this "
                    "repo does not ship, so ask a maintainer to redraw it; never edit "
                    "the SVG by hand.",
                )


if __name__ == "__main__":
    unittest.main()
