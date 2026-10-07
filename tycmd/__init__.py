"""A python wrapper for tycmd."""

import json
import logging
import re
import shutil
import sys
import sysconfig
from functools import cache
from os import PathLike
from pathlib import Path
from subprocess import PIPE, CalledProcessError, Popen
from threading import Thread
from typing import Literal, TypeAlias, TypedDict, cast

log = logging.getLogger(__name__)

Family: TypeAlias = Literal['Teensy', 'Generic']
"""Family of a board."""

RtcMode: TypeAlias = Literal['local', 'utc', 'none']
"""How to set the board's real-time clock on upload."""

Capability: TypeAlias = Literal[
    'unique',
    'void',
    'run',
    'upload',
    'encrypt',
    'lock',
    'locked',
    'reset',
    'rtc',
    'reboot',
    'serial',
]
"""Something a board can do or be:

- ``'unique'``: the serial number tells this board apart from others
- ``'void'``: the board is in a secured (HAB) state where a bootloader has to be sent first
- ``'run'``: the board is running firmware
- ``'upload'``: the board accepts firmware uploads
- ``'encrypt'``: the board supports encrypted firmware
- ``'lock'``: the board's encryption key can be locked
- ``'locked'``: the board's encryption key is locked
- ``'reset'``: the board can be reset
- ``'rtc'``: the board's real-time clock can be set
- ``'reboot'``: the board can be rebooted into its bootloader
- ``'serial'``: the board has a serial interface
"""

BoardAction: TypeAlias = Literal['add', 'change', 'miss', 'remove']
"""Event that produced a board entry."""

__version__ = '0.3.1'
_TYCMD_VERSION = '0.9.9'
_TYCMD_NAME = 'tycmd.exe' if sys.platform == 'win32' else 'tycmd'
_OPTIONAL_BOARD_KEYS = ('serial', 'description', 'public_key_hash')
_RE_STRIP_TAG = re.compile(r'(^\s*\w+@\w+-\w+\s+)')  # match board tag
_RE_VERSION = re.compile(r'\d+\.\d+\.\d+')  # match semantic version number


class Board(TypedDict):
    """A :class:`~typing.TypedDict` describing a board."""

    action: BoardAction
    """The event that produced this entry."""
    tag: str
    """The entries' tag, e.g. ``'12345678-Teensy@1'``."""
    model: str
    """Model name of the board, e.g. ``'Teensy 4.1'``."""
    location: str
    """USB location of the board, e.g. ``'usb-3-2'``."""
    capabilities: list[Capability]
    """Capabilities of the board."""
    interfaces: list[list[str]]  # [name, path]
    """Interfaces of the board as ``[name, path]`` pairs, e.g. ``['Serial', '/dev/ttyACM0']``."""
    serial: str | None
    """Serial number of the board, or :py:obj:`None` if it does not report one."""
    description: str | None
    """Description of the board as reported by USB, or :py:obj:`None`."""
    public_key_hash: str | None
    """Hash of the public key used for encrypted firmware, or :py:obj:`None`."""


def upload(
    filename: PathLike | str,
    *,
    serial: str | None = None,
    port: str | None = None,
    family: Family | None = None,
    check: bool = True,
    reset: bool = True,
    rtc: RtcMode = 'local',
    log_level: int = logging.INFO,
):
    """
    Upload firmware to board. Status messages are logged.

    Parameters
    ----------
    filename : PathLike or str
        Path to the firmware file.
    serial : str, optional
        Serial number of the targeted board.
    port : str, optional
        Port of the targeted board.
    family : Family, optional
        Family of the targeted board.
    check : bool, default: True
        Check if the board is compatible before upload.
    reset : bool, default: True
        Reset the device once the upload is finished.
    rtc : RtcMode, default: 'local'
        Set RTC if supported: 'local', 'utc' or 'none'.
    log_level : int, default: :py:data:`logging.INFO`
        Log level.
    """
    filename = str(_parse_firmware_file(filename))
    args = ['upload']
    if not check:
        args.append('--nocheck')
    if not reset:
        args.append('--noreset')
    if log_level == logging.NOTSET:
        args.append('--quiet')
    args.extend(['--rtc', rtc, filename])
    _call_tycmd(args, port=port, serial=serial, family=family, log_level=log_level)


def reset(
    *,
    serial: str | None = None,
    port: str | None = None,
    family: Family | None = None,
    bootloader: bool = False,
    log_level: int = logging.INFO,
) -> None:
    """
    Reset board. Status messages are logged.

    Parameters
    ----------
    serial : str, optional
        Serial number of targeted board.

    port : str, optional
        Port of targeted board.

    family : Family, optional
        Family of the targeted board.

    bootloader : bool, default: False
        Switch board to bootloader if True.

    log_level : int, default: :py:data:`logging.INFO`
        Log level.
    """
    args = ['reset']
    if bootloader:
        args.append('--bootloader')
    if log_level == logging.NOTSET:
        args.append('--quiet')
    _call_tycmd(args, serial=serial, port=port, log_level=log_level)


def identify(filename: PathLike | str) -> list[str]:
    """
    Identify models compatible with firmware.

    Parameters
    ----------
    filename : PathLike | str
        Path to the firmware file.

    Returns
    -------
    list[str]
        List of models compatible with firmware.
    """
    filename = str(_parse_firmware_file(filename))
    json_str = _call_tycmd(args=['identify', filename, '--json'], raise_on_stderr=True)
    json_str = json_str.replace('\\', '\\\\')
    output = json.loads(json_str)
    return output.get('models', [])


def list_boards() -> list[Board]:
    """
    List available boards.

    Returns
    -------
    list[Board]
        List of available boards. ``serial``, ``description`` and ``public_key_hash`` are :py:obj:`None`
        if the board does not report them.
    """
    output = _call_tycmd(['list', '-O', 'json', '-v'])
    return [_normalize_board(board) for board in json.loads(output)]


def version() -> str:
    """
    Return version information from tycmd binary.

    Returns
    -------
    str
        The version of tycmd.

    Raises
    ------
    RuntimeError
        If the version string could not be determined.
    """
    output = _call_tycmd(['--version'])
    match = _RE_VERSION.search(output)
    if match is None:
        raise ChildProcessError('Could not determine tycmd version')
    else:
        return match.group()


def _normalize_board(board: dict) -> Board:
    """Fill in the keys that tycmd omits when a board doesn't report them."""
    for key in _OPTIONAL_BOARD_KEYS:
        board.setdefault(key, None)
    return cast(Board, board)


def _parse_firmware_file(filename: PathLike | str) -> Path:
    filepath = Path(filename).resolve()
    if not filepath.exists():
        raise FileNotFoundError(filepath)
    if filepath.is_dir():
        raise IsADirectoryError(filepath)
    if len(ext := filepath.suffixes) == 0 or ext[-1].lower() not in (
        '.hex',
        '.elf',
        '.ehex',
    ):
        raise ValueError(f"Firmware '{filepath.name}' uses unrecognized extension")
    return filepath


def _call_tycmd(
    args: list[str],
    *,
    serial: str | None = None,
    port: str | None = None,
    family: str | None = None,
    raise_on_stderr: bool = False,
    log_level: int = logging.NOTSET,
) -> str:
    args = _assemble_args(args, serial=serial, family=family, port=port)
    log.debug(f'Calling subprocess: {" ".join(args)}')

    # Call tycmd
    with Popen(args, stdout=PIPE, stderr=PIPE, text=True, bufsize=1) as p:
        if log_level > logging.NOTSET:
            assert p.stdout is not None
            assert p.stderr is not None
            stdout_stream, stderr_stream = p.stdout, p.stderr

            stderr_chunks: list[str] = []
            stderr_thread = Thread(
                target=lambda: stderr_chunks.append(''.join(stderr_stream)), daemon=True
            )
            stderr_thread.start()

            stdout = ''
            for line in stdout_stream:
                line = _RE_STRIP_TAG.sub('', line, count=1).strip()
                log.log(level=log_level, msg=line)
                stdout += line

            stderr_thread.join()
            stderr = stderr_chunks[0]
        else:
            stdout, stderr = p.communicate()
            stdout = _RE_STRIP_TAG.sub('', stdout).strip()
    stderr = _RE_STRIP_TAG.sub('', stderr).strip()

    # Raise non-zero exit codes as a RuntimeError
    if p.returncode != 0:
        e = CalledProcessError(returncode=p.returncode, cmd=p.args)
        raise ChildProcessError(stderr) from e

    # tycmd doesn't always set a non-negative exit code when an error occurs.
    # If raise_on_stderr is True and the subprocess' stderr is not None we'll
    # still raise a ChildProcessError despite the exit code being 0.
    if raise_on_stderr and len(stderr) > 0:
        raise ChildProcessError(stderr)

    return stdout


@cache
def _resolve_tycmd() -> str:
    """Resolve the path to the bundled tycmd binary."""
    candidate = Path(sysconfig.get_path('scripts')) / _TYCMD_NAME
    if candidate.is_file():
        return str(candidate)
    return shutil.which(_TYCMD_NAME) or _TYCMD_NAME


def _assemble_args(
    args: list[str],
    port: str | None = None,
    serial: str | None = None,
    family: str | None = None,
) -> list[str]:
    output = [_resolve_tycmd(), *args]
    if any(x is not None for x in (port, serial, family)):
        tag = ''.join(
            (
                '' if serial is None else str(serial),
                '' if family is None else f'-{family}',
                '' if port is None else f'@{port}',
            )
        )
        output.append(f'--board={tag}')
    return output
