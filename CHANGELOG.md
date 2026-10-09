# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

### Added

- `TycmdError`, a `subprocess.CalledProcessError` raised whenever tycmd fails - its message is
  tycmd's own error message
- `Board` type for the entries returned by `list_boards()`, and `Capability`, `BoardAction` and
  `RtcMode` type aliases
- warnings from tycmd are logged as they occur, and requests to press the board's button are
  always logged as warnings, regardless of `log_level`

### Changed

- **breaking:** options of `upload()` and `reset()` are keyword-only, and `upload()`'s
  `reset_board` and `rtc_mode` arguments are renamed to `reset` and `rtc`
- **breaking:** failing tycmd calls raise `TycmdError` instead of `ChildProcessError`
- **breaking:** `identify()` raises `ValueError` if tycmd can't load the firmware file
- **breaking:** `version()` raises `RuntimeError` if the version can't be determined
- **breaking:** `upload()` raises `ValueError` for an invalid `rtc` value
- **breaking:** only the tycmd binary bundled with tycmd-wrapper is used - there is no fallback to
  a `tycmd` on the PATH anymore
- `list_boards()` always includes `serial` and `description`, set to `None` if a board doesn't
  report them
- `FileNotFoundError` and `IsADirectoryError` for firmware files carry `errno` and `filename`
- tycmd's output is decoded as UTF-8, independent of the system's locale
- tycmd is killed if a call is interrupted (e.g. by `KeyboardInterrupt`) instead of being waited
  for
- tycmd-wrapper is a package (`tycmd/`) instead of a single module
- improved typehints
- simplified workflow for publishing to PyPI

### Removed

- support for `.ehex` firmware files, which the bundled tycmd 0.9.9 can't load

### Fixed

- `version()` returns the complete version string, including suffixes such as `-beta.2`
- board tags are stripped from every line of tycmd's output, including tags of boards without a
  serial number, of secondary interfaces and of generic boards
- `identify()` handles backslashes, tabs and newlines in firmware filenames
- type checkers now pick up the `py.typed` marker

## [0.3.1] - 2026-09-27

### Changed

- dropped platform whitelist from the build script

## [0.3.0] - 2026-09-27

### Changed

- macOS now ships as two separate, correctly-tagged wheels (`macosx_11_0_arm64` and
  `macosx_11_0_x86_64`) instead of a single x86_64-only wheel, fixing installation on Apple Silicon
- Linux arm64 is now a published wheel target
- the `tycmd` binary is no longer committed to the repository; it's built from source during CI
  (and on demand for local installs) instead

## [0.2.1] - 2024-08-06

### Changed

- changed default log-level for reset() and upload() to INFO
- added a few examples to README.md

## [0.2.0] - 2024-08-06

### Added

- upload() method for uploading firmware file
- status messages will be sent to log

### Changed

- moved 'port' kwarg ahead of 'serial'
- raise ChildProcessError instead of RuntimeError

## [0.1.2] - 2024-07-11

### Changed

- dropped 'verbose' argument from list_boards()
- dropped 'full' argument from version()

## [0.1.1] - 2024-07-11

### Added

- identify() method for identifying a firmware file

## [0.1.0] - 2024-07-11

_First release._


[Unreleased]: https://github.com/int-brain-lab/tycmd-wrapper/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.3.1
[0.3.0]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.3.0
[0.2.1]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.2.1
[0.2.0]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.2.0
[0.1.2]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.1.2
[0.1.1]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.1.1
[0.1.0]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.1.0
