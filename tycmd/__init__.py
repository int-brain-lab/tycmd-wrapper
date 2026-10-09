"""A Python wrapper for tycmd."""

import errno
import json
import logging
import re
import shlex
import sys
from functools import cache, partial
from importlib.metadata import PackageNotFoundError, files
from os import PathLike, strerror
from pathlib import Path
from subprocess import PIPE, CalledProcessError, Popen
from threading import Thread
from typing import IO, Literal, TypeAlias, TypedDict, cast, get_args

log = logging.getLogger(__name__)

RtcMode: TypeAlias = Literal['local', 'utc', 'none']
"""How to set the board's real-time clock on upload."""

Capability: TypeAlias = Literal[
    'unique', 'run', 'upload', 'reset', 'rtc', 'reboot', 'serial'
]
"""Something a board can do or be:

- ``'unique'``: the serial number tells this board apart from others
- ``'run'``: the board is running firmware
- ``'upload'``: the board is in bootloader mode and accepts firmware uploads
- ``'reset'``: the board is in bootloader mode and can be reset to start its firmware
- ``'rtc'``: the board's real-time clock can be set when resetting after an upload
- ``'reboot'``: the running board can be rebooted into its bootloader
- ``'serial'``: the board has a serial interface
"""

BoardAction: TypeAlias = Literal['add', 'change', 'miss', 'remove']
"""Event that produced a board entry."""

__version__ = '0.3.1'
"""Version of tycmd-wrapper."""
_TYCMD_VERSION = '0.9.9'
"""Version of the bundled tycmd binary."""
_TYCMD_NAME = 'tycmd.exe' if sys.platform == 'win32' else 'tycmd'
"""File name of the tycmd binary."""
_OPTIONAL_BOARD_KEYS = ('serial', 'description')
"""Keys of :class:`Board` that tycmd omits if a board doesn't report them."""
_RE_STRIP_TAG = re.compile(r'^[ \t]*\w+@.+? {2}')
"""Matches the ``<task>@<board tag>`` prefix of tycmd's task messages."""
_RE_USER_ACTION = re.compile(r'\bpress button\b', re.IGNORECASE)
"""Matches status messages asking the user to press the board's button."""
_VALID_FIRMWARE_EXT = ('.hex', '.elf')
"""File extensions of supported firmware files."""


class TycmdError(CalledProcessError):
    """Raised when tycmd exits with an error."""

    def __str__(self) -> str:
        """Return tycmd's error message, or the exit status if there is none."""
        return self.stderr or super().__str__()


class Board(TypedDict):
    """A board as reported by tycmd."""

    action: BoardAction
    """Event that produced this entry."""
    tag: str
    """Tag of the board, e.g. ``'12345678-Teensy'``."""
    serial: str | None
    """Serial number, or :py:obj:`None` if not reported."""
    description: str | None
    """USB description, or :py:obj:`None` if not reported."""
    model: str
    """Model name, e.g. ``'Teensy 4.1'``."""
    location: str
    """USB location, e.g. ``'usb-3-2'``."""
    capabilities: list[Capability]
    """Capabilities of the board."""
    interfaces: list[list[str]]
    """Interfaces as ``[name, path]`` pairs, e.g. ``['Serial', '/dev/ttyACM0']``."""


def upload(
    filename: PathLike | str,
    *,
    serial: str | None = None,
    port: str | None = None,
    check: bool = True,
    reset: bool = True,
    rtc: RtcMode = 'local',
    log_level: int = logging.INFO,
) -> None:
    """
    Upload firmware to a board.

    Unless ``check`` is False, tycmd first checks that the firmware is compatible with
    the board. It then reboots the board into its bootloader if needed, uploads the
    firmware and, unless ``reset`` is False, resets the board to start it. Without
    ``serial`` and ``port``, the first board detected is used.

    Parameters
    ----------
    filename : PathLike | str
        Path to the firmware file.
    serial : str, optional
        Serial number of the board.
    port : str, optional
        Port of the board.
    check : bool, default: True
        Check that the firmware is compatible with the board.
    reset : bool, default: True
        Reset the board after the upload.
    rtc : RtcMode, default: 'local'
        Set the board's real-time clock, if it has one: 'local', 'utc' or 'none'.
    log_level : int, default: :py:data:`logging.INFO`
        Log level for tycmd's status messages, :py:data:`logging.NOTSET` to disable.
        Warnings are always logged as such.

    Raises
    ------
    FileNotFoundError
        If the firmware file does not exist.
    IsADirectoryError
        If the firmware path is a directory.
    ValueError
        If the firmware file has an unsupported extension or ``rtc`` is invalid.
    TycmdError
        If tycmd fails.

    Warnings
    --------
    If the board can't be rebooted into its bootloader, tycmd waits until the board's
    button is pressed. This is logged as a warning.

    Examples
    --------
    Upload to the board on a specific port:

    >>> tycmd.upload('blink.hex', port='/dev/ttyACM0')

    Upload to the board with a specific serial number, without resetting it:

    >>> tycmd.upload('blink.hex', serial='14014980', reset=False)
    """
    if rtc not in (rtc_modes := get_args(RtcMode)):
        raise ValueError(f'rtc must be one of {", ".join(rtc_modes)}, not {rtc!r}')
    filename = str(_parse_firmware_file(filename))
    args = ['upload']
    if not check:
        args.append('--nocheck')
    if not reset:
        args.append('--noreset')
    args.extend(['--rtc', rtc, filename])
    _call_tycmd(args, serial=serial, port=port, log_level=log_level)


def reset(
    *,
    serial: str | None = None,
    port: str | None = None,
    bootloader: bool = False,
    log_level: int = logging.INFO,
) -> None:
    """
    Reset a board.

    A running board is first rebooted into its bootloader, then reset to start its
    firmware. With ``bootloader``, it is only rebooted into its bootloader. Without
    ``serial`` and ``port``, the first board detected is used.

    Parameters
    ----------
    serial : str, optional
        Serial number of the board.
    port : str, optional
        Port of the board.
    bootloader : bool, default: False
        Reboot into the bootloader instead.
    log_level : int, default: :py:data:`logging.INFO`
        Log level for tycmd's status messages, :py:data:`logging.NOTSET` to disable.
        Warnings are always logged as such.

    Raises
    ------
    TycmdError
        If tycmd fails.

    Examples
    --------
    Restart the firmware of the board with a specific serial number:

    >>> tycmd.reset(serial='14014980')

    Reboot it into its bootloader instead:

    >>> tycmd.reset(serial='14014980', bootloader=True)
    """
    args = ['reset']
    if bootloader:
        args.append('--bootloader')
    _call_tycmd(args, serial=serial, port=port, log_level=log_level)


def identify(filename: PathLike | str) -> list[str]:
    """
    Identify the board models compatible with a firmware file.

    Only the file is inspected - no board needs to be connected.

    Parameters
    ----------
    filename : PathLike | str
        Path to the firmware file.

    Returns
    -------
    list[str]
        Names of the compatible models, empty if there are none.

    Raises
    ------
    FileNotFoundError
        If the firmware file does not exist.
    IsADirectoryError
        If the firmware path is a directory.
    ValueError
        If the firmware file has an unsupported extension or can't be loaded, or if
        tycmd's output can't be parsed (e.g. if the filename contains ``"``).
    TycmdError
        If tycmd fails.

    Examples
    --------
    List the models a firmware file is compatible with:

    >>> tycmd.identify('blink.hex')
    ['Teensy 4.0', 'Teensy 4.0 (beta 1)']
    """
    filename = str(_parse_firmware_file(filename))
    json_str = _call_tycmd(['identify', filename, '--json'])

    # tycmd doesn't escape the filename in its JSON output: escaping backslashes covers
    # Windows paths, strict=False covers control characters, a '"' remains unsupported
    json_str = json_str.replace('\\', '\\\\')
    try:
        output = json.loads(json_str, strict=False)
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse tycmd's output for '{filename}'") from e

    # tycmd exits with 0 even if it can't load the firmware
    if 'error' in output:
        raise ValueError(output['error'])
    return output.get('models', [])


def list_boards() -> list[Board]:
    """
    List the available boards.

    Includes boards in bootloader mode. See :class:`Board` for the details reported.

    Returns
    -------
    list[Board]
        Available boards.

    Raises
    ------
    TycmdError
        If tycmd fails.

    Examples
    --------
    Get the serial numbers of all available boards:

    >>> [board['serial'] for board in tycmd.list_boards()]
    ['3576040', '14014980']
    """
    output = _call_tycmd(['list', '-O', 'json', '-v'])
    return [_normalize_board(board) for board in json.loads(output)]


def version() -> str:
    """
    Return the version of the bundled tycmd binary.

    Returns
    -------
    str
        Version of tycmd, e.g. ``'0.9.9'``.

    Raises
    ------
    RuntimeError
        If the version can't be determined.

    Examples
    --------
    Check the version of the bundled tycmd binary:

    >>> tycmd.version()
    '0.9.9'
    """
    try:
        output = _call_tycmd(['--version'])
        _, tycmd_version = output.split(maxsplit=1)
    except Exception as e:
        raise RuntimeError('Could not determine the version of tycmd') from e
    return tycmd_version


def _normalize_board(board: dict) -> Board:
    """Add the keys that tycmd omits if a board doesn't report them."""
    for key in _OPTIONAL_BOARD_KEYS:
        board.setdefault(key, None)
    return cast('Board', board)


def _parse_firmware_file(filename: PathLike | str) -> Path:
    """Return the resolved path of a firmware file, or raise if it's not usable."""
    filepath = Path(filename).resolve()
    if not filepath.exists():
        raise FileNotFoundError(errno.ENOENT, strerror(errno.ENOENT), str(filepath))
    if filepath.is_dir():
        raise IsADirectoryError(errno.EISDIR, strerror(errno.EISDIR), str(filepath))
    if filepath.suffix.lower() not in _VALID_FIRMWARE_EXT:
        raise ValueError(
            f"'{filepath.name}' has unrecognized extension "
            f'(supported: {", ".join(_VALID_FIRMWARE_EXT)})'
        )
    return filepath


def _call_tycmd(
    args: list[str],
    *,
    serial: str | None = None,
    port: str | None = None,
    family: str | None = None,
    log_level: int = logging.NOTSET,
) -> str:
    """Run tycmd, log its output and return its stdout."""
    args = _assemble_args(args, serial=serial, port=port, family=family)
    log.debug('Calling subprocess: %s', shlex.join(args))

    # stdout (status messages) is logged at log_level, stderr (warnings and errors) at
    # WARNING - stderr is read in a thread, so neither pipe can fill up and block tycmd
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    with Popen(args, stdout=PIPE, stderr=PIPE, encoding='utf-8', errors='replace') as p:
        assert p.stdout is not None
        assert p.stderr is not None
        stderr_thread = Thread(
            target=partial(_consume_pipe, p.stderr, stderr_lines, logging.WARNING)
        )
        stderr_thread.start()
        try:
            _consume_pipe(p.stdout, stdout_lines, log_level)
        except BaseException:
            p.kill()  # tycmd may never exit on its own, e.g. awaiting a button press
            raise
        finally:
            stderr_thread.join()  # before the with-block closes the pipes
    stdout = '\n'.join(stdout_lines).strip()
    stderr = '\n'.join(stderr_lines).strip()

    if p.returncode != 0:
        raise TycmdError(p.returncode, p.args, output=stdout, stderr=stderr)
    return stdout


def _consume_pipe(stream: IO[str], lines: list[str], log_level: int) -> None:
    """Strip, collect and log each line - button prompts always at WARNING."""
    for line in stream:
        stripped_line = _RE_STRIP_TAG.sub('', line).strip()
        lines.append(stripped_line)
        if not stripped_line:
            continue
        if _RE_USER_ACTION.search(stripped_line):
            log.warning(stripped_line)
        elif log_level > logging.NOTSET:
            log.log(log_level, stripped_line)


@cache
def _resolve_tycmd() -> str:
    """Return the path of the bundled tycmd binary."""
    try:
        record = files('tycmd-wrapper') or []
    except PackageNotFoundError:
        record = []
    for file in record:
        if (
            file.name == _TYCMD_NAME
            and (path := Path(file.locate()).resolve()).is_file()
        ):
            return str(path)
    raise FileNotFoundError(
        f'Could not find the {_TYCMD_NAME} binary bundled with tycmd-wrapper - '
        'try reinstalling the package'
    )


def _assemble_args(
    args: list[str],
    serial: str | None = None,
    port: str | None = None,
    family: str | None = None,
) -> list[str]:
    """Return the tycmd command line, with a ``--board`` tag if a board is given."""
    output = [_resolve_tycmd(), *args]
    if any(x is not None for x in (serial, port, family)):
        tag = ''.join(
            (
                '' if serial is None else serial,
                '' if family is None else f'-{family}',
                '' if port is None else f'@{port}',
            )
        )
        output.append(f'--board={tag}')
    return output
