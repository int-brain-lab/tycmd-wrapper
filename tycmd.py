"""A python wrapper for tycmd."""

from pathlib import Path
from subprocess import check_output, CalledProcessError
import json
import re
from logging import getLogger

__version__ = "0.1.1"
_TYCMD_VERSION = "0.9.9"

log = getLogger(__name__)


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
    return_string = _call_tycmd(args=["identify", filename, "--json", "-qqq"])
    return_string = return_string.replace("\\", "\\\\")
    output = json.loads(return_string)
    if "error" in output:
        raise RuntimeError(output["error"])
    return output.get("models", [])


def list_boards(verbose: bool = True) -> list[dict]:
    """
    List available boards.

    Parameters
    ----------
    verbose : bool, optional
        If True, include detailed information about devices. Default is True.

    Returns
    -------
    list[dict]
        List of available devices.
    """
    args = ["tycmd", "list", "-O", "json"] + (["-v"] if verbose else [])
    return json.loads(check_output(args, text=True))


def version(full: bool = False) -> str:
    """
    Return version information from tycmd.

    Parameters
    ----------
    full : bool, optional
        If True, return the full version string as returned by the tycmd binary. If
        False, return only the version number. Default is False.

    Returns
    -------
    str
        The version of tycmd.
    """
    output = _call_tycmd(["--version"])
    if full:
        return output.strip()
    else:
        if (match := re.search(r"\d+\.\d+\.\d+", output)) is None:
            return ""
        return match.group()


def reset(
    serial: str | None = None, port: str | None = None, bootloader: bool = False
) -> bool:
    """
    Reset board.

    Parameters
    ----------
    serial : str, optional
        Serial number of board to be reset.

    port : str, optional
        Port of board to be reset.

    bootloader : bool, optional
        Switch board to bootloader if True. Default is False.

    Returns
    -------
    bool
        True if board was reset successfully, False otherwise.
    """
    try:
        _call_tycmd(
            ["reset"] + (["-b"] if bootloader else []), serial=serial, port=port
        )
        return True
    except CalledProcessError:
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
) -> str:
    tag = _assemble_tag(serial=serial, family=family, port=port)
    args = ["tycmd"] + args + tag
    log.debug(" ".join(args))
    return check_output(args, text=True)


def _assemble_tag(
    serial: str | None = None, family: str | None = None, port: str | None = None
) -> list[str]:
    tag = "" if serial is None else str(serial)
    tag += "" if family is None else f"-{family}"
    tag += "" if port is None else f"@{port}"
    return ["-B", tag] if len(tag) > 0 else []
