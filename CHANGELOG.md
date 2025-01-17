# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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


[0.2.1]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.2.1
[0.2.0]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.2.0
[0.1.2]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.1.2
[0.1.1]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.1.1
[0.1.0]: https://github.com/int-brain-lab/tycmd-wrapper/releases/tag/v0.1.0
