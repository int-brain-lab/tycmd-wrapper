import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

import tycmd

BLINK40_HEX = Path(__file__).parent.joinpath('blink40.hex').resolve()
BLINK41_HEX = Path(__file__).parent.joinpath('blink41.hex').resolve()


@pytest.fixture(autouse=True)
def _clear_resolve_tycmd_cache():
    # _resolve_tycmd is cached, so a real resolution from one test would otherwise leak into
    # the next (e.g. into test__resolve_tycmd's own mocked scenarios).
    tycmd._resolve_tycmd.cache_clear()
    yield
    tycmd._resolve_tycmd.cache_clear()


@pytest.fixture
def mock_Popen():
    with patch('tycmd.Popen', autospec=True) as mock_Popen:
        context = mock_Popen.return_value.__enter__.return_value

        def set_pipes(stdout: list[str] | None = None, stderr: list[str] | None = None):
            context.stdout = stdout if stdout is not None else []
            context.stderr = stderr if stderr is not None else []
            context.communicate.return_value = (
                '\n'.join(context.stdout),
                '\n'.join(context.stderr),
            )

        def set_returncode(returncode: int = 0):
            context.returncode = returncode

        mock_Popen.set_pipes = set_pipes
        mock_Popen.set_returncode = set_returncode
        mock_Popen.set_pipes([], [])
        mock_Popen.set_returncode(0)

        yield mock_Popen


def test_upload(mock_Popen, caplog):
    mock_Popen.set_pipes(stdout=['output'])
    caplog.set_level(logging.INFO)
    tycmd.upload(BLINK40_HEX, check=True, reset_board=True)
    assert '--nocheck' not in mock_Popen.call_args[0][0]
    assert '--noreset' not in mock_Popen.call_args[0][0]
    assert '--rtc' in mock_Popen.call_args[0][0]
    assert '--quiet' not in mock_Popen.call_args[0][0]
    assert len(caplog.records) > 0
    assert all(x.levelname == 'INFO' for x in caplog.records)

    caplog.clear()
    tycmd.upload(BLINK40_HEX, check=False, reset_board=False, log_level=logging.NOTSET)
    assert '--nocheck' in mock_Popen.call_args[0][0]
    assert '--noreset' in mock_Popen.call_args[0][0]
    assert '--rtc' in mock_Popen.call_args[0][0]
    assert '--quiet' in mock_Popen.call_args[0][0]
    assert len(caplog.records) == 0


def test_reset(mock_Popen, caplog):
    mock_Popen.set_pipes(['status'], [])
    caplog.set_level(logging.INFO)
    tycmd.reset(bootloader=True, log_level=logging.NOTSET)
    mock_Popen.assert_called_once()
    assert '--bootloader' in mock_Popen.call_args[0][0]
    assert len(caplog.records) == 0

    tycmd.reset()
    assert '--bootloader' not in mock_Popen.call_args[0][0]
    assert len(caplog.records) > 0
    assert all(x.levelname == 'INFO' for x in caplog.records)

    mock_Popen.set_returncode(1)
    with pytest.raises(ChildProcessError):
        tycmd.reset()


def test_identify():
    with TemporaryDirectory() as temp_directory:
        firmware_file = Path(temp_directory).joinpath('firmware.hex')
        firmware_file.touch()
        with pytest.raises(ChildProcessError):
            tycmd.identify(firmware_file)
    assert 'Teensy 4.0' in tycmd.identify(BLINK40_HEX)
    assert 'Teensy 4.1' in tycmd.identify(BLINK41_HEX)


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
    assert output[0]['serial'] == '12345678'

    mock_Popen.set_pipes(['[\n]\n'], [])
    output = tycmd.list_boards()
    assert isinstance(output, list)
    assert len(output) == 0


def test_version():
    assert tycmd.version() == tycmd._TYCMD_VERSION
    with (
        patch('tycmd._call_tycmd', return_value='invalid') as _,
        pytest.raises(ChildProcessError),
    ):
        tycmd.version()


def test__parse_firmware_file():
    with TemporaryDirectory() as temp_directory:
        with pytest.raises(IsADirectoryError):
            tycmd._parse_firmware_file(temp_directory)
        firmware_file = Path(temp_directory).joinpath('firmware')
        with pytest.raises(FileNotFoundError):
            tycmd._parse_firmware_file(firmware_file)
        firmware_file.touch()
        with pytest.raises(ValueError):
            tycmd._parse_firmware_file(firmware_file)
        firmware_file = firmware_file.with_suffix('.HEX')
        firmware_file.touch()
        assert tycmd._parse_firmware_file(firmware_file).samefile(firmware_file)
        assert tycmd._parse_firmware_file(str(firmware_file)).samefile(firmware_file)


def test__call_tycmd(mock_Popen):
    mock_Popen.set_pipes(['status'], ['error!'])
    tycmd._call_tycmd([], raise_on_stderr=False)
    with pytest.raises(ChildProcessError):
        tycmd._call_tycmd([], raise_on_stderr=True)

    mock_Popen.set_pipes(['status'], [])
    mock_Popen.set_returncode(-1)
    with pytest.raises(ChildProcessError):
        tycmd._call_tycmd([])


def test__assemble_args():
    output = tycmd._assemble_args(args=[], serial='serial')
    assert '-B serial' in ' '.join(output)
    output = tycmd._assemble_args(args=[], family='family')
    assert '-B -family' in ' '.join(output)
    output = tycmd._assemble_args(args=[], port='port')
    assert '-B @port' in ' '.join(output)
    output = tycmd._assemble_args(
        args=['some_argument'], serial='serial', family='family', port='port'
    )
    assert '-B serial-family@port' in ' '.join(output)
    assert Path(output[0]).name == tycmd._TYCMD_NAME
    assert 'some_argument' in output


def test__resolve_tycmd(tmp_path):
    # _resolve_tycmd is cached (it's invariant for the life of the process), so each scenario
    # below needs a fresh cache or it'd just keep returning the first call's result.
    with patch('tycmd.sysconfig.get_path', return_value=str(tmp_path)):
        # no binary at the expected "scripts" location -> falls back to a PATH lookup
        with patch('tycmd.shutil.which', return_value=None):
            assert tycmd._resolve_tycmd() == tycmd._TYCMD_NAME
        tycmd._resolve_tycmd.cache_clear()
        with patch('tycmd.shutil.which', return_value='/usr/bin/tycmd'):
            assert tycmd._resolve_tycmd() == '/usr/bin/tycmd'
        tycmd._resolve_tycmd.cache_clear()

        # binary present at the expected "scripts" location -> used directly, no PATH lookup
        candidate = tmp_path / tycmd._TYCMD_NAME
        candidate.touch()
        with patch('tycmd.shutil.which') as mock_which:
            assert tycmd._resolve_tycmd() == str(candidate)
            mock_which.assert_not_called()
