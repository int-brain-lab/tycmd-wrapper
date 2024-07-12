"""A python wrapper for tycmd."""

from pathlib import Path
from subprocess import check_output, CalledProcessError
import json
import re
from logging import getLogger

__version__ = "0.2.0"
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


def list_boards() -> list[dict]:
    """
    List available boards.

    Returns
    -------
    list[dict]
        List of available devices.
    """
    args = ["tycmd", "list", "-O", "json", "-v"]
    return_string = check_output(args, text=True)
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
        raise RuntimeError("Could not determine tycmd version")
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
        Port of board to be reset.

    serial : str, optional
        Serial number of board to be reset.

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
    port: str | None = None, serial: str | None = None, family: str | None = None
) -> list[str]:
    tag = "" if serial is None else str(serial)
    tag += "" if family is None else f"-{family}"
    tag += "" if port is None else f"@{port}"
    return ["-B", tag] if len(tag) > 0 else []
