import logging
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

import tycmd

BLINK40_HEX = Path(__file__).parent.joinpath('blink40.hex').resolve()
BLINK41_HEX = Path(__file__).parent.joinpath('blink41.hex').resolve()


@pytest.fixture(autouse=True)
def _clear_resolve_tycmd_cache():
    # _resolve_tycmd is cached, so a real resolution from one test would otherwise leak
    # into the next (e.g. into test__resolve_tycmd's own mocked scenarios).
    tycmd._resolve_tycmd.cache_clear()
    yield
    tycmd._resolve_tycmd.cache_clear()


@pytest.fixture
def mock_popen():
    with patch('tycmd.Popen', autospec=True) as mock_popen:
        context = mock_popen.return_value.__enter__.return_value

        def set_pipes(stdout: list[str] | None = None, stderr: list[str] | None = None):
            # like real pipes, iterating yields lines that end with a newline
            context.stdout = [f'{line}\n' for line in stdout or []]
            context.stderr = [f'{line}\n' for line in stderr or []]
            context.communicate.return_value = (
                ''.join(context.stdout),
                ''.join(context.stderr),
            )

        def set_returncode(returncode: int = 0):
            context.returncode = returncode

        mock_popen.set_pipes = set_pipes
        mock_popen.set_returncode = set_returncode
        mock_popen.set_pipes([], [])
        mock_popen.set_returncode(0)

        yield mock_popen


def test_upload(mock_popen, caplog):
    mock_popen.set_pipes(stdout=['output'])
    caplog.set_level(logging.INFO)
    tycmd.upload(BLINK40_HEX, check=True, reset=True)
    assert '--nocheck' not in mock_popen.call_args[0][0]
    assert '--noreset' not in mock_popen.call_args[0][0]
    assert '--rtc' in mock_popen.call_args[0][0]
    assert '--quiet' not in mock_popen.call_args[0][0]
    assert len(caplog.records) > 0
    assert all(x.levelname == 'INFO' for x in caplog.records)

    caplog.clear()
    tycmd.upload(BLINK40_HEX, check=False, reset=False, log_level=logging.NOTSET)
    assert '--nocheck' in mock_popen.call_args[0][0]
    assert '--noreset' in mock_popen.call_args[0][0]
    assert '--rtc' in mock_popen.call_args[0][0]
    assert '--quiet' in mock_popen.call_args[0][0]
    assert len(caplog.records) == 0


def test_reset(mock_popen, caplog):
    mock_popen.set_pipes(['status'], [])
    caplog.set_level(logging.INFO)
    tycmd.reset(bootloader=True, log_level=logging.NOTSET)
    mock_popen.assert_called_once()
    assert '--bootloader' in mock_popen.call_args[0][0]
    assert len(caplog.records) == 0

    tycmd.reset()
    assert '--bootloader' not in mock_popen.call_args[0][0]
    assert len(caplog.records) > 0
    assert all(x.levelname == 'INFO' for x in caplog.records)

    mock_popen.set_returncode(1)
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


def test_list_boards(mock_popen):
    stdout = (
        '[\n  {"action": "add", "tag": "12345678-Teensy", "serial": "12345678", '
        '"description": "USB Serial", "model": "Teensy 4.1", "location": "usb-3-3", '
        '"capabilities": ["unique", "run", "rtc", "reboot", "serial"], '
        '"interfaces": [["Serial", "/dev/ttyACM0"]]}\n]\n'
    )
    mock_popen.set_pipes([stdout], [])
    output = tycmd.list_boards()
    assert isinstance(output, list)
    assert isinstance(output[0], dict)
    assert output[0]['serial'] == '12345678'

    # keys that tycmd omits are filled in with None
    stdout = (
        '[\n  {"action": "add", "tag": "12345678-Teensy", "model": "Teensy 4.1", '
        '"location": "usb-3-3", "capabilities": [], "interfaces": []}\n]\n'
    )
    mock_popen.set_pipes([stdout], [])
    board = tycmd.list_boards()[0]
    assert board['serial'] is None
    assert board['description'] is None
    assert board['tag'] == '12345678-Teensy'

    mock_popen.set_pipes(['[\n]\n'], [])
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


@pytest.mark.parametrize(
    ('line', 'expected'),
    [
        # task messages, prefixed with '<task>@<board tag>' right-aligned to 28 chars
        (
            "       reset@11383920-Teensy  Resetting board '11383920-Teensy'",
            "Resetting board '11383920-Teensy'",
        ),
        (
            '             upload@?-Teensy  Uploading...',
            'Uploading...',
        ),
        (
            '     reset@12345678-Teensy@1  Sending reset command',
            'Sending reset command',
        ),
        (
            '  reset@ABC123-Arduino LLC  Cannot reset board',
            'Cannot reset board',
        ),
        (
            'upload@123456789012-Teensy  Board  is  busy',
            'Board  is  busy',
        ),
        # untagged output is left alone
        (
            "Board 'nope' not found",
            "Board 'nope' not found",
        ),
        (
            "Board 'foo@bar'  not found",
            "Board 'foo@bar'  not found",
        ),
        (
            'tycmd 0.9.9',
            'tycmd 0.9.9',
        ),
        (
            '  {"action": "add", "tag": "1-Teensy@1"}',
            '  {"action": "add", "tag": "1-Teensy@1"}',
        ),
    ],
)
def test__re_strip_tag(line, expected):
    assert tycmd._RE_STRIP_TAG.sub('', line) == expected


def test__re_strip_tag_multiline():
    output = (
        "       reset@11383920-Teensy  Resetting board '11383920-Teensy' (Teensy 3.1)\n"
        '       reset@11383920-Teensy  Triggering board reboot\n'
        '\n'
        '       reset@11383920-Teensy  Sending reset command\n'
    )
    assert tycmd._RE_STRIP_TAG.sub('', output) == (
        "Resetting board '11383920-Teensy' (Teensy 3.1)\n"
        'Triggering board reboot\n'
        '\n'
        'Sending reset command\n'
    )


def test__call_tycmd(mock_popen):
    mock_popen.set_pipes(['status'], ['error!'])
    tycmd._call_tycmd([], raise_on_stderr=False)
    with pytest.raises(ChildProcessError):
        tycmd._call_tycmd([], raise_on_stderr=True)

    mock_popen.set_pipes(['status'], [])
    mock_popen.set_returncode(-1)
    with pytest.raises(ChildProcessError):
        tycmd._call_tycmd([])


def test__call_tycmd_strips_tags(mock_popen, caplog):
    stdout = [
        "       reset@11383920-Teensy  Resetting board '11383920-Teensy' (Teensy 3.1)",
        '       reset@11383920-Teensy  Sending reset command',
    ]
    stderr = [
        '       reset@11383920-Teensy  First error',
        '       reset@11383920-Teensy  Second error',
    ]

    # without logging: every line is stripped, not just the first one
    mock_popen.set_pipes(stdout, [])
    assert tycmd._call_tycmd([]) == (
        "Resetting board '11383920-Teensy' (Teensy 3.1)\nSending reset command"
    )

    # with logging: each line is logged without its tag
    caplog.set_level(logging.INFO)
    tycmd._call_tycmd([], log_level=logging.INFO)
    assert [r.getMessage() for r in caplog.records] == [
        "Resetting board '11383920-Teensy' (Teensy 3.1)",
        'Sending reset command',
    ]

    # error messages are stripped as well, on every line
    mock_popen.set_pipes([], stderr)
    mock_popen.set_returncode(1)
    for log_level in (logging.NOTSET, logging.INFO):
        with pytest.raises(ChildProcessError) as exc_info:
            tycmd._call_tycmd([], log_level=log_level)
        assert str(exc_info.value) == 'First error\nSecond error'


@pytest.mark.parametrize('log_level', [logging.NOTSET, logging.INFO])
def test__call_tycmd_decoding(log_level):
    # run a real subprocess (Python standing in for tycmd) that writes UTF-8 plus a byte
    # that isn't valid UTF-8 to both stdout and stderr
    script = (
        'import sys; '
        "sys.stdout.buffer.write(b'caf\\xc3\\xa9 M\\xfcller\\n'); "
        "sys.stderr.buffer.write(b'caf\\xc3\\xa9 M\\xfcller\\n'); "
        'sys.exit(int(sys.argv[1]))'
    )
    with patch('tycmd._resolve_tycmd', return_value=sys.executable):
        output = tycmd._call_tycmd(['-c', script, '0'], log_level=log_level)
        assert output.startswith('café M�ller')
        with pytest.raises(ChildProcessError, match='café M�ller'):
            tycmd._call_tycmd(['-c', script, '1'], log_level=log_level)


def test__assemble_args():
    assert '--board=serial' in tycmd._assemble_args(args=[], serial='serial')
    assert '--board=-family' in tycmd._assemble_args(args=[], family='family')
    assert '--board=@port' in tycmd._assemble_args(args=[], port='port')
    assert '--board' not in ''.join(tycmd._assemble_args(args=[]))

    output = tycmd._assemble_args(
        args=['some_argument'], serial='serial', family='family', port='port'
    )
    assert '--board=serial-family@port' in output
    assert '-B' not in output
    assert Path(output[0]).name == tycmd._TYCMD_NAME
    assert 'some_argument' in output


def test__resolve_tycmd(tmp_path):
    # _resolve_tycmd is cached (it's invariant for the life of the process), so each
    # scenario below needs a fresh cache or it'd just keep returning the first call's
    # result.
    with patch('tycmd.sysconfig.get_path', return_value=str(tmp_path)):
        # no binary at the expected "scripts" location -> falls back to a PATH lookup
        with patch('tycmd.shutil.which', return_value=None):
            assert tycmd._resolve_tycmd() == tycmd._TYCMD_NAME
        tycmd._resolve_tycmd.cache_clear()
        with patch('tycmd.shutil.which', return_value='/usr/bin/tycmd'):
            assert tycmd._resolve_tycmd() == '/usr/bin/tycmd'
        tycmd._resolve_tycmd.cache_clear()

        # binary present at the expected "scripts" location -> used directly,
        # no PATH lookup
        candidate = tmp_path / tycmd._TYCMD_NAME
        candidate.touch()
        with patch('tycmd.shutil.which') as mock_which:
            assert tycmd._resolve_tycmd() == str(candidate)
            mock_which.assert_not_called()
