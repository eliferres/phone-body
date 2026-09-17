"""The demo receipt: demo/transcript.json must be what the commands really print.

Every entry is replayed with bash in a scratch copy of the repo, under the
setup the README's By hand block runs first. Only machine paths and wall-clock
values are normalized before comparing; everything else must match exactly.

Regenerate the transcript from a real run (never by hand):

    UPDATE_DEMO_TRANSCRIPT=1 python3 -m unittest tests.test_demo_transcript
"""

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

# Each pattern is anchored to the one place a volatile value appears, so a
# changed word, file name or winner around it still fails the comparison.
VOLATILE = [
    (re.compile(r"^(resolved: )\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ ", re.MULTILINE), r"\1<now> "),
    (re.compile(r"\(mtime \d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z\)"), "(mtime <mtime>)"),
    (re.compile(r"\bdaily/\d{4}-\d\d-\d\d\.md: "), "daily/<today>.md: "),
    (re.compile(r"(memory/learned\.md: )\d{4}-\d\d-\d\d \u2014 "), "\\1<today> \u2014 "),
]

# Rows of the picture: long commands wrap at this width into " \"-ended chunks.
PICTURE_CMD_WIDTH = 58
ELLIPSIS = "…"
SVG_NS = "{http://www.w3.org/2000/svg}"


def without_volatile(text):
    for pattern, replacement in VOLATILE:
        text = pattern.sub(replacement, text)
    return text


def without_paths(text, pairs):
    for real, placeholder in pairs:
        text = text.replace(real, placeholder)
    return text


def replay(entries):
    """Run every entry in order in one scratch copy; return (out, status) pairs
    with machine paths already swapped for their placeholders."""
    scratch = Path(tempfile.mkdtemp())
    try:
        checkout = scratch / "checkout"
        shutil.copytree(
            REPO,
            checkout,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "build", "*.egg-info"),
        )
        work = scratch / "work"
        work.mkdir()
        shutil.copytree(checkout / "demo" / "brain", work / "desk-brain")
        shutil.copytree(checkout / "demo" / "brain", work / "phone-brain")

        # Longest first, so the checkout path is not half-replaced by a prefix.
        pairs = sorted(
            {
                (str(checkout), CHECKOUT_PLACEHOLDER),
                (str(checkout.resolve()), CHECKOUT_PLACEHOLDER),
                (str(work), WORK_PLACEHOLDER),
                (str(work.resolve()), WORK_PLACEHOLDER),
            },
            key=lambda pair: -len(pair[0]),
        )
        env = dict(os.environ, work=str(work))
        env.pop("BRAIN_PATH", None)
        # The transcript says python3; make that the interpreter running the suite.
        env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), env.get("PATH", "")])

        results = []
        for entry in entries:
            ran = subprocess.run(
                ["bash", "-c", entry["cmd"]],
                cwd=checkout,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            results.append((without_paths(ran.stdout, pairs), ran.returncode))
        return results
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


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
                    without_volatile(entry["out"]),
                    without_volatile(out),
                    f"entry {number} output: expected (transcript) first, actual second",
                )
                self.assertEqual(entry["status"], status, f"entry {number} exit status")

    def test_transcript_holds_no_machine_paths(self):
        for entry in self.entries:
            for field in ("cmd", "out"):
                self.assertNotRegex(entry[field], r"/Users/|/private/var|/var/folders|/tmp/tmp")

    def test_every_picture_row_comes_from_the_transcript(self):
        out_lines = [line for entry in self.entries for line in entry["out"].splitlines()]
        cmd_rows = [row for entry in self.entries for row in wrapped_command_rows(entry["cmd"])]
        rows = picture_rows(PICTURE)
        self.assertTrue(rows, "the picture has no text rows")
        for row in rows:
            shown = row[: -len(ELLIPSIS)] if row.endswith(ELLIPSIS) else row
            with self.subTest(row=row):
                self.assertTrue(
                    any(line.startswith(shown) for line in out_lines + cmd_rows),
                    f"picture row {row!r} is not a prefix of any transcript line or command row",
                )


if __name__ == "__main__":
    unittest.main()
