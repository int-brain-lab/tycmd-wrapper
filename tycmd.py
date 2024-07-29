"""A python wrapper for tycmd."""

from pathlib import Path
from subprocess import CalledProcessError, PIPE, DEVNULL, run
import json
import re
from logging import getLogger
from typing import Literal, IO

__version__ = "0.2.0"
_TYCMD_VERSION = "0.9.9"

log = getLogger(__name__)


def upload(
    filename: Path | str,
    port: str | None = None,
    serial: str | None = None,
    check: bool = True,
    reset_board: bool = True,
    rtc_mode: Literal["local", "utc", "none"] = "local",
    quiet: bool = False,
):
    """
    Upload firmware to board.

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

    quiet : bool, optional
        Disable output. Defaults to False.
    """
    filename = str(_parse_firmware_file(filename))
    args = ["upload"]
    if not check:
        args.append("--nocheck")
    if not reset_board:
        args.append("--noreset")
    if quiet:
        args.append("--quiet")
    args.extend(["--rtc", rtc_mode, filename])
    _call_tycmd(args, port=port, serial=serial, stdout=DEVNULL if quiet else None)


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
    return_string = _call_tycmd(args=["identify", filename, "--json"])
    return_string = return_string.replace("\\", "\\\\")
    output = json.loads(return_string)
    if "error" in output:
        raise RuntimeError(output["error"])
    return output.get("models", [])


def list_boards() -> list[dict]:
    """
    List available boards.

    Returns
    -------
    list[dict]
        List of available devices.
    """
    args = ["list", "-O", "json", "-v"]
    return_string = _call_tycmd(args)
    # return_string = check_output(args, text=True)
    return json.loads(return_string)


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


def reset(
    port: str | None = None, serial: str | None = None, bootloader: bool = False
) -> bool:
    """
    Reset board.

    Parameters
    ----------
    port : str, optional
        Port of targeted board.

    serial : str, optional
        Serial number of targeted board.

    bootloader : bool, optional
        Switch board to bootloader if True. Default is False.

    Returns
    -------
    bool
        True if board was reset successfully, False otherwise.
    """
    try:
        _call_tycmd(
            ["reset"] + (["--bootloader"] if bootloader else []),
            serial=serial,
            port=port,
        )
        return True
    except ChildProcessError:
        return False


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
    stdout: None | int | IO = PIPE,
    raise_on_stderr: bool = False,
) -> str:
    tag = _assemble_tag(serial=serial, family=family, port=port)
    args = ["tycmd"] + tag + args
    log.debug(f"Calling subprocess: {' '.join(args)}")

    # call tycmd and raise non-zero exit codes as a RuntimeError
    try:
        p = run(args, stdout=stdout, stderr=PIPE, check=True, text=True)
    except CalledProcessError as e:
        raise ChildProcessError(str.strip(e.stderr or "")) from e

    # tycmd doesn't always set a non-negative exit code when an error occurs. If
    # raise_on_stderr is True and the subprocess' stderr is not None we'll still raise a
    # ChildProcessError despite the exit code being 0.
    if raise_on_stderr and isinstance(p.stderr, str):
        raise ChildProcessError(p.stderr.strip())

    return p.stdout.strip() if isinstance(p.stdout, str) else ""


def _assemble_tag(
    port: str | None = None, serial: str | None = None, family: str | None = None
) -> list[str]:
    tag = "" if serial is None else str(serial)
    tag += "" if family is None else f"-{family}"
    tag += "" if port is None else f"@{port}"
    return ["-B", tag] if len(tag) > 0 else []
