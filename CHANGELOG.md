# Changelog

## Unreleased

### Added
- Added packaging: `pipx install git+https://github.com/eliferres/phone-body` installs the `phone-body-desktop`, `phone-body-bot` and `phone-body-brain` commands, each with `--version`.

### Changed
- Changed the README file tree to say again what the old table said: `sync.sh` supports `--dry-run`, the demo vault is fictional content, and the phone body is long-polling shaped and offline by design.
- Renamed the `skeleton/` folder to the `phone_body` package so an install cannot shadow another package; run the bodies with `python3 -m phone_body.body_desktop` and `python3 -m phone_body.body_bot`, and sync with `phone_body/sync.sh`.
- Changed the README shape: it opens with the demo, then install, then how the pieces fit together and how sync settles a conflict; the file table is now a short tree.
- Changed a wrong `--brain` or `--messages` path to print one line and exit 2 instead of a traceback.

### Fixed
- Fixed the demo receipt starting mid-session: demo/transcript.json now records the three setup lines of the README walkthrough too, so the recorded session is the whole session and the test hides no setup of its own.
- Fixed the demo receipt test accepting any date in the brain's output: it now checks the real current date instead of blanking both sides, so a frozen or wrong date fails even after a regenerate.
- Fixed the demo receipt test going red after its own regenerate command: the picture check compared timestamps that a fresh run always changes, and its failure message now says the picture is redrawn by a maintainer, never edited by hand.
- Fixed demo/transcript.json, which was missing the desktop body's closing prompt line and had stale timestamps; a new test replays every entry and fails if the shipped output drifts from a real run.
- Fixed CI running only the unit tests: it now also runs `./demo/run.sh`, the README's first command, and checks `sync.sh` parses.

## [1.1.0](https://github.com/eliferres/phone-body/releases/tag/v1.1.0) - 2026-09-03

### Added
- Added a terminal demo to the README's first screen, showing body_desktop.py teaching a fact, a real sync.sh run, and body_bot.py answering with what the desktop learned.
- Added tests that run sync.sh end to end: a losing write overwritten on disk, a locally deleted file drifting back, and usage errors.
- Added coverage for bot message handling: a multi-message batch, blank-line filtering, and the stdin fallback.
- Added demo/run.sh, a runnable version of the quick start's own ten lines.
- Added macos-latest to the CI matrix alongside ubuntu-latest.

### Changed
- Changed the README to lead with the one-command quick start, with the original steps kept in a By Hand section right below it.

## [1.0.0](https://github.com/eliferres/phone-body/releases/tag/v1.0.0) - 2026-08-31

First public release.
