import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

import tycmd

BLINK40_HEX = Path(__file__).parent.joinpath("blink40.hex").resolve()
BLINK41_HEX = Path(__file__).parent.joinpath("blink41.hex").resolve()


@pytest.fixture
def mock_Popen():
    with patch("tycmd.Popen", autospec=True) as mock_Popen:
        context = mock_Popen.return_value.__enter__.return_value

        def set_pipes(stdout: list[str], stderr: list[str]):
            context.stdout = stdout
            context.stderr = stderr
            context.communicate.return_value = (
                "\n".join(context.stdout),
                "\n".join(context.stderr),
            )

        def set_returncode(returncode: int):
            context.returncode = returncode

        mock_Popen.set_pipes = set_pipes
        mock_Popen.set_returncode = set_returncode
        mock_Popen.set_pipes([], [])
        mock_Popen.set_returncode(0)

        yield mock_Popen


def test_upload(mock_Popen):
    tycmd.upload(BLINK40_HEX, check=True, reset_board=True)
    assert "--nocheck" not in mock_Popen.call_args[0][0]
    assert "--noreset" not in mock_Popen.call_args[0][0]
    assert "--rtc" in mock_Popen.call_args[0][0]
    assert "--quiet" not in mock_Popen.call_args[0][0]
    tycmd.upload(BLINK40_HEX, check=False, reset_board=False, log_level=logging.NOTSET)
    assert "--nocheck" in mock_Popen.call_args[0][0]
    assert "--noreset" in mock_Popen.call_args[0][0]
    assert "--rtc" in mock_Popen.call_args[0][0]
    assert "--quiet" in mock_Popen.call_args[0][0]


def test_reset(mock_Popen, caplog):
    output = tycmd.reset(bootloader=True, log_level=0)
    mock_Popen.assert_called_once()
    assert "--bootloader" in mock_Popen.call_args[0][0]
    assert len(caplog.records) == 0
    assert output is None

    mock_Popen.set_pipes(["status"], [])
    tycmd.reset(log_level=30)
    assert "--bootloader" not in mock_Popen.call_args[0][0]
    assert "status" in caplog.text

    mock_Popen.set_returncode(1)
    with pytest.raises(ChildProcessError):
        tycmd.reset()


def test_identify():
    with TemporaryDirectory() as temp_directory:
        firmware_file = Path(temp_directory).joinpath("firmware.hex")
        firmware_file.touch()
        with pytest.raises(ChildProcessError):
            tycmd.identify(firmware_file)
    assert "Teensy 4.0" in tycmd.identify(BLINK40_HEX)
    assert "Teensy 4.1" in tycmd.identify(BLINK41_HEX)


def test_list_boards(mock_Popen):
    stdout = (
        '[\n  {"action": "add", "tag": "12345678-Teensy", "serial": "12345678", '
        '"description": "USB Serial", "model": "Teensy 4.1", "location": "usb-3-3", '
        '"capabilities": ["unique", "run", "rtc", "reboot", "serial"], '
        '"interfaces": [["Serial", "/dev/ttyACM0"]]}\n]\n'
    )
    mock_Popen.set_pipes([stdout], [])
    output = tycmd.list_boards()
    assert isinstance(output, list)
    assert isinstance(output[0], dict)
    assert output[0]["serial"] == "12345678"

    mock_Popen.set_pipes(["[\n]\n"], [])
    output = tycmd.list_boards()
    assert isinstance(output, list)
    assert len(output) == 0


def test_version():
    assert tycmd.version() == tycmd._TYCMD_VERSION
    with (
        patch("tycmd._call_tycmd", return_value="invalid") as _,
        pytest.raises(ChildProcessError),
    ):
        tycmd.version()


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


def test__call_tycmd(mock_Popen):
    mock_Popen.set_pipes(["status"], ["error!"])
    tycmd._call_tycmd([], raise_on_stderr=False)
    with pytest.raises(ChildProcessError):
        tycmd._call_tycmd([], raise_on_stderr=True)

    mock_Popen.set_pipes(["status"], [])
    mock_Popen.set_returncode(-1)
    with pytest.raises(ChildProcessError):
        tycmd._call_tycmd([])


def test__assemble_args():
    output = tycmd._assemble_args(args=[], serial="serial")
    assert "-B serial" in " ".join(output)
    output = tycmd._assemble_args(args=[], family="family")
    assert "-B -family" in " ".join(output)
    output = tycmd._assemble_args(args=[], port="port")
    assert "-B @port" in " ".join(output)
    output = tycmd._assemble_args(
        args=["some_argument"], serial="serial", family="family", port="port"
    )
    assert "-B serial-family@port" in " ".join(output)
    assert "tycmd" in output
    assert "some_argument" in output
