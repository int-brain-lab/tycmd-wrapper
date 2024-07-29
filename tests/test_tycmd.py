from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from subprocess import CompletedProcess, CalledProcessError

import pytest

import tycmd

BLINK40_HEX = Path(__file__).parent.joinpath("blink40.hex").resolve()
BLINK41_HEX = Path(__file__).parent.joinpath("blink41.hex").resolve()


@pytest.fixture
def mock_run():
    with patch("tycmd.run") as mock_run:
        yield mock_run


def test_upload(mock_run):
    mock_run.return_value = CompletedProcess([], 0)
    tycmd.upload(BLINK40_HEX, check=False, reset_board=False, quiet=True)
    mock_run.assert_called_once()
    assert "--nocheck" in mock_run.call_args[0][0]
    assert "--noreset" in mock_run.call_args[0][0]
    assert "--quiet" in mock_run.call_args[0][0]


def test_identify():
    with TemporaryDirectory() as temp_directory:
        firmware_file = Path(temp_directory).joinpath("firmware.hex")
        firmware_file.touch()
        with pytest.raises(RuntimeError):
            tycmd.identify(firmware_file)
    assert "Teensy 4.0" in tycmd.identify(BLINK40_HEX)


def test_list_boards(mock_run):
    stdout = (
        '[\n  {"action": "add", "tag": "12345678-Teensy", "serial": "12345678", '
        '"description": "USB Serial", "model": "Teensy 4.1", "location": "usb-3-3", '
        '"capabilities": ["unique", "run", "rtc", "reboot", "serial"], '
        '"interfaces": [["Serial", "/dev/ttyACM0"]]}\n]\n'
    )
    mock_run.return_value = CompletedProcess([], 0, stdout=stdout)
    output = tycmd.list_boards()
    assert isinstance(output, list)
    assert isinstance(output[0], dict)
    assert output[0]["serial"] == "12345678"

    mock_run.return_value = CompletedProcess([], 0, stdout="[\n]\n")
    output = tycmd.list_boards()
    assert isinstance(output, list)
    assert len(output) == 0


def test_version():
    assert tycmd.version() == tycmd._TYCMD_VERSION
    with (
        patch("tycmd.run", return_value=CompletedProcess([], 0, stdout="invalid")) as _,
        pytest.raises(ChildProcessError),
    ):
        tycmd.version()


def test_reset(mock_run):
    mock_run.return_value = CompletedProcess([], 0)
    output = tycmd.reset(bootloader=True)
    mock_run.assert_called_once()
    assert "--bootloader" in mock_run.call_args[0][0]
    assert output is True
    mock_run.side_effect = CalledProcessError(-1, [])
    output = tycmd.reset()
    assert output is False


def test__parse_firmware_file():
    with TemporaryDirectory() as temp_directory:
        with pytest.raises(IsADirectoryError):
            tycmd._parse_firmware_file(temp_directory)
        firmware_file = Path(temp_directory).joinpath("firmware")
        with pytest.raises(FileNotFoundError):
            tycmd._parse_firmware_file(firmware_file)
        firmware_file.touch()
        with pytest.raises(ValueError):
            tycmd._parse_firmware_file(firmware_file)
        firmware_file = firmware_file.with_suffix(".hex")
        firmware_file.touch()
        assert tycmd._parse_firmware_file(firmware_file).samefile(firmware_file)
        assert tycmd._parse_firmware_file(str(firmware_file)).samefile(firmware_file)


def test__assemble_tag():
    output = tycmd._assemble_tag(serial="serial")
    assert output == ["-B", "serial"]
    output = tycmd._assemble_tag(family="family")
    assert output == ["-B", "-family"]
    output = tycmd._assemble_tag(port="port")
    assert output == ["-B", "@port"]
    output = tycmd._assemble_tag(serial="serial", family="family", port="port")
    assert output == ["-B", "serial-family@port"]
    output = tycmd._assemble_tag()
    assert output == []
