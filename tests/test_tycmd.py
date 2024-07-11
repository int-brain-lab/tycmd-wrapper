from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

import tycmd
import re


BLINK_HEX = Path(__file__).parent.joinpath("blink.hex").resolve()


@pytest.fixture
def mock_check_output():
    with patch("tycmd.check_output") as mock_check_output:
        yield mock_check_output


def test_identify():
    with TemporaryDirectory() as temp_directory:
        firmware_file = Path(temp_directory).joinpath("firmware.hex")
        firmware_file.touch()
        with pytest.raises(RuntimeError):
            tycmd.identify(firmware_file)
    assert "Teensy 4.0" in tycmd.identify(BLINK_HEX)


def test_list_boards(mock_check_output):
    mock_check_output.return_value = (
        '[\n  {"action": "add", "tag": "12345678-Teensy", "serial": "12345678", '
        '"description": "USB Serial", "model": "Teensy 4.1", "location": "usb-3-3", '
        '"capabilities": ["unique", "run", "rtc", "reboot", "serial"], '
        '"interfaces": [["Serial", "/dev/ttyACM0"]]}\n]\n'
    )
    output = tycmd.list_boards()
    mock_check_output.assert_called_once_with(
        ["tycmd", "list", "-O", "json", "-v"], text=True
    )
    assert isinstance(output, list)
    assert isinstance(output[0], dict)
    assert output[0]["serial"] == "12345678"

    mock_check_output.return_value = "[\n]\n"
    output = tycmd.list_boards()
    assert isinstance(output, list)
    assert len(output) == 0


def test_version():
    output = tycmd.version(full=True)
    assert isinstance(output, str)
    match = re.search(r"^.+(\d+\.\d+\.\d+)", output)
    assert match is not None
    assert match.groups()[0] == tycmd._TYCMD_VERSION
    assert tycmd.version(full=False) == tycmd._TYCMD_VERSION


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
