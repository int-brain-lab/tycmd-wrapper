# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

### Added

- allow for filtering by board family
- `Board` TypedDict describing the entries returned by `list_boards()`

### Changed

- simplified workflow for publishing to PyPI

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


[0.3.1]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.3.1
[0.3.0]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.3.0
[0.2.1]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.2.1
[0.2.0]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.2.0
[0.1.2]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.1.2
[0.1.1]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.1.1
[0.1.0]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.1.0
