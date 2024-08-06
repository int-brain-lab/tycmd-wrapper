"""A python wrapper for tycmd."""

from pathlib import Path
from subprocess import PIPE, Popen, CalledProcessError
import json
import re
import logging
from typing import Literal

log = logging.getLogger(__name__)

__version__ = "0.2.0"
_TYCMD_VERSION = "0.9.9"
RE_STRIP_TAG = re.compile(r"(^\s*\w+@\w+-\w+\s+)")  # match board tag


def upload(
    filename: Path | str,
    port: str | None = None,
    serial: str | None = None,
    check: bool = True,
    reset_board: bool = True,
    rtc_mode: Literal["local", "utc", "none"] = "local",
    log_level: int = logging.WARNING,
):
    """
    Upload firmware to board. Status messages are logged.

    Parameters
    ----------
    filename : Path | str
        Path to the firmware file.

    port : str, optional
        Port of targeted board.

    serial : str, optional
        Serial number of targeted board.

    check : bool, optional
        Check if board is compatible before upload. Defaults to True.

    reset_board : bool, optional
        Reset the device once the upload is finished. Defaults to True.

    rtc_mode : str, optional
        Set RTC if supported: 'local' (default), 'utc' or 'none'.

    log_level : int, optional
        Logging level. Defaults to logging.WARNING.
    """
    filename = str(_parse_firmware_file(filename))
    args = ["upload"]
    if not check:
        args.append("--nocheck")
    if not reset_board:
        args.append("--noreset")
    if log_level == logging.NOTSET:
        args.append("--quiet")
    args.extend(["--rtc", rtc_mode, filename])
    _call_tycmd(args, port=port, serial=serial, log_level=log_level)


def reset(
    port: str | None = None,
    serial: str | None = None,
    bootloader: bool = False,
    log_level: int = logging.WARNING,
) -> None:
    """
    Reset board. Status messages are logged.

    Parameters
    ----------
    port : str, optional
        Port of targeted board.

    serial : str, optional
        Serial number of targeted board.

    bootloader : bool, optional
        Switch board to bootloader if True. Default is False.

    log_level : int, optional
        Logging level. Defaults to logging.WARNING.
    """
    args = ["reset"]
    if bootloader:
        args.append("--bootloader")
    if log_level == logging.NOTSET:
        args.append("--quiet")
    _call_tycmd(args, serial=serial, port=port, log_level=log_level)


def identify(filename: Path | str) -> list[str]:
    """
    Identify models compatible with firmware.

    Parameters
    ----------
    filename : Path | str
        Path to the firmware file.

    Returns
    -------
    list[str]
        List of models compatible with firmware.
    """
    filename = str(_parse_firmware_file(filename))
    json_str = _call_tycmd(args=["identify", filename, "--json"], raise_on_stderr=True)
    json_str = json_str.replace("\\", "\\\\")
    output = json.loads(json_str)
    return output.get("models", [])


def list_boards() -> list[dict]:
    """
    List available boards.

    Returns
    -------
    list[dict]
        List of available devices.
    """
    output = _call_tycmd(["list", "-O", "json", "-v"])
    return json.loads(output)


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
    output = _call_tycmd(["--version"])
    match = re.search(r"\d+\.\d+\.\d+", output)
    if match is None:
        raise ChildProcessError("Could not determine tycmd version")
    else:
        return match.group()


def _parse_firmware_file(filename: str | Path) -> Path:
    filepath = Path(filename).resolve()
    if not filepath.exists():
        raise FileNotFoundError(filepath)
    if filepath.is_dir():
        raise IsADirectoryError(filepath)
    if len(ext := filepath.suffixes) == 0 or ext[-1] not in (".hex", ".elf", ".ehex"):
        raise ValueError(f"Firmware '{filepath.name}' uses unrecognized extension")
    return filepath


def _call_tycmd(
    args: list[str],
    serial: str | None = None,
    family: str | None = None,
    port: str | None = None,
    raise_on_stderr: bool = False,
    log_level: int = logging.NOTSET,
) -> str:
    args = _assemble_args(args, serial=serial, family=family, port=port)
    log.debug(f"Calling subprocess: {' '.join(args)}")

    # Call tycmd
    with Popen(args, stdout=PIPE, stderr=PIPE, text=True, bufsize=1) as p:
        if log_level > logging.NOTSET:
            stdout = ""
            assert p.stdout is not None
            for line in p.stdout:
                line = re.sub(
                    pattern=RE_STRIP_TAG, repl="", string=line, count=1
                ).strip()
                log.log(level=log_level, msg=line)
                stdout += line
            _, stderr = p.communicate()
        else:
            stdout, stderr = p.communicate()
            stdout = re.sub(pattern=RE_STRIP_TAG, repl="", string=stdout).strip()
    stderr = re.sub(pattern=RE_STRIP_TAG, repl="", string=stderr).strip()

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


def _assemble_args(
    args: list[str],
    port: str | None = None,
    serial: str | None = None,
    family: str | None = None,
) -> list[str]:
    output = ["tycmd", *args]
    if any((port, serial, family)):
        tag = "" if serial is None else str(serial)
        tag += "" if family is None else f"-{family}"
        tag += "" if port is None else f"@{port}"
        output.extend(["-B", tag])
    return output
