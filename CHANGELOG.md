# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

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
