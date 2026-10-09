import errno
import logging
import sys
import threading
import time
from pathlib import Path
from subprocess import CalledProcessError, Popen
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import tycmd

BLINK40_HEX = Path(__file__).parent.joinpath('blink40.hex').resolve()
BLINK41_HEX = Path(__file__).parent.joinpath('blink41.hex').resolve()

# arguments for running Python as a stand-in for tycmd: isolated mode and no site
# import, so starting the interpreter is fast and unaffected by the environment
PYTHON_ARGS = ['-I', '-S', '-c']


@pytest.fixture(autouse=True)
def _clear_resolve_tycmd_cache():
    # _resolve_tycmd is cached, so a real resolution from one test would otherwise leak
    # into the next (e.g. into test_resolve_tycmd's own mocked scenarios).
    tycmd._resolve_tycmd.cache_clear()
    yield
    tycmd._resolve_tycmd.cache_clear()


@pytest.fixture
def mock_popen():
    with patch('tycmd.Popen', spec=Popen) as mock_popen:
        context = mock_popen.return_value.__enter__.return_value

        def set_pipes(stdout: list[str] | None = None, stderr: list[str] | None = None):
            # like real pipes, iterating yields lines that end with a newline
            context.stdout = [f'{line}\n' for line in stdout or []]
            context.stderr = [f'{line}\n' for line in stderr or []]

        def set_returncode(returncode: int = 0):
            context.returncode = returncode

        mock_popen.set_pipes = set_pipes
        mock_popen.set_returncode = set_returncode
        mock_popen.set_pipes([], [])
        mock_popen.set_returncode(0)

        yield mock_popen


class TestUpload:
    def test_upload(self, mock_popen, caplog):
        """Upload options are passed to tycmd and status messages are logged."""
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
        assert '--quiet' not in mock_popen.call_args[0][0]
        assert len(caplog.records) == 0

    @pytest.mark.parametrize('rtc', ['local', 'utc', 'none'])
    def test_upload_rtc(self, mock_popen, rtc):
        """Each RTC mode is passed to tycmd."""
        tycmd.upload(BLINK40_HEX, rtc=rtc)
        args = mock_popen.call_args[0][0]
        assert args[args.index('--rtc') + 1] == rtc

    @pytest.mark.parametrize('rtc', ['bogus', 'LOCAL', '', None])
    def test_upload_rtc_invalid(self, mock_popen, rtc):
        """An invalid RTC mode raises ValueError without calling tycmd."""
        with pytest.raises(ValueError, match='rtc must be one of local, utc, none'):
            tycmd.upload(BLINK40_HEX, rtc=rtc)
        mock_popen.assert_not_called()


class TestReset:
    def test_reset(self, mock_popen, caplog):
        """Reset options are passed to tycmd, and failures raise TycmdError."""
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
        with pytest.raises(tycmd.TycmdError):
            tycmd.reset()


class TestIdentify:
    def test_identify(self):
        """Compatible models are identified, and invalid firmware raises ValueError."""
        with TemporaryDirectory() as temp_directory:
            firmware_file = Path(temp_directory).joinpath('firmware.hex')
            firmware_file.touch()
            with pytest.raises(ValueError, match='Missing EOF record'):
                tycmd.identify(firmware_file)
        assert 'Teensy 4.0' in tycmd.identify(BLINK40_HEX)
        assert 'Teensy 4.1' in tycmd.identify(BLINK41_HEX)

    @pytest.mark.skipif(sys.platform == 'win32', reason='invalid characters on Windows')
    @pytest.mark.parametrize(
        'name', ['back\\slash.hex', 'tab\tname.hex', 'new\nline.hex']
    )
    def test_identify_special_characters(self, tmp_path, name):
        """Filenames that tycmd doesn't escape in its JSON output are handled."""
        firmware_file = tmp_path / name
        firmware_file.write_bytes(BLINK40_HEX.read_bytes())
        assert 'Teensy 4.0' in tycmd.identify(firmware_file)

    def test_identify_unparsable_output(self):
        """Unparsable output (e.g. due to a '"' in the filename) raises ValueError."""
        output = '{"file": "/tmp/quote".hex", "models": ["Teensy 4.0"]}'
        with (
            patch('tycmd._call_tycmd', return_value=output),
            pytest.raises(ValueError, match="Could not parse tycmd's output"),
        ):
            tycmd.identify(BLINK40_HEX)


class TestListBoards:
    def test_list_boards(self, mock_popen):
        """Boards are parsed from tycmd's JSON output, with omitted keys set to None."""
        stdout = (
            '[\n  {"action": "add", "tag": "12345678-Teensy", "serial": "12345678", '
            '"description": "USB Serial", "model": "Teensy 4.1", '
            '"location": "usb-3-3", '
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


class TestVersion:
    def test_version(self):
        """The bundled binary reports the version that tycmd-wrapper expects."""
        binary_version = tycmd._call_tycmd(['--version']).strip().split(maxsplit=1)[-1]
        assert tycmd._TYCMD_VERSION == binary_version
        assert tycmd.version() == tycmd._TYCMD_VERSION

    @pytest.mark.parametrize(
        ('output', 'expected'),
        [
            ('tycmd 0.9.9', '0.9.9'),
            ('tycmd 0.9.10-beta.2', '0.9.10-beta.2'),
            ('tycmd.exe 0.9.9', '0.9.9'),
            ('tycmd (unknown version)', '(unknown version)'),
        ],
    )
    def test_version_parsing(self, output, expected):
        """The version is everything after the executable name, including suffixes."""
        with patch('tycmd._call_tycmd', return_value=output):
            assert tycmd.version() == expected

    @pytest.mark.parametrize('output', ['', 'tycmd', '0.9.9'])
    def test_version_parsing_invalid(self, output):
        """Output without a version raises RuntimeError."""
        with (
            patch('tycmd._call_tycmd', return_value=output),
            pytest.raises(RuntimeError, match='Could not determine the version'),
        ):
            tycmd.version()


class TestParseFirmwareFile:
    def test_parse_firmware_file(self):
        """Missing files, directories and unsupported extensions raise errors."""
        with TemporaryDirectory() as temp_directory:
            with pytest.raises(IsADirectoryError) as exc_info:
                tycmd._parse_firmware_file(temp_directory)
            assert exc_info.value.errno == errno.EISDIR
            assert exc_info.value.filename == str(Path(temp_directory).resolve())
            firmware_file = Path(temp_directory).joinpath('firmware')
            with pytest.raises(FileNotFoundError) as exc_info:
                tycmd._parse_firmware_file(firmware_file)
            assert exc_info.value.errno == errno.ENOENT
            assert exc_info.value.filename == str(firmware_file.resolve())
            firmware_file.touch()
            with pytest.raises(ValueError, match=r'\(supported: \.hex, \.elf\)'):
                tycmd._parse_firmware_file(firmware_file)
            firmware_file = firmware_file.with_suffix('.HEX')
            firmware_file.touch()
            assert tycmd._parse_firmware_file(firmware_file).samefile(firmware_file)
            assert tycmd._parse_firmware_file(str(firmware_file)).samefile(
                firmware_file
            )

    @pytest.mark.parametrize(
        'name', ['blink.hex', 'blink.HEX', 'blink.elf', 'blink.ino.hex', 'v1.2.elf']
    )
    def test_parse_firmware_file_valid_extension(self, tmp_path, name):
        """Supported extensions are accepted, regardless of case and other dots."""
        (firmware_file := tmp_path / name).touch()
        assert tycmd._parse_firmware_file(firmware_file) == firmware_file.resolve()

    @pytest.mark.parametrize(
        'name',
        [
            'blink',  # no extension
            '.hex',  # dotfile without extension
            'blink.bin',
            'blink.hex.bak',  # only the last extension counts, like in tycmd
            'blink.ehex',  # encrypted firmware, not supported by tycmd 0.9.9
        ],
    )
    def test_parse_firmware_file_invalid_extension(self, tmp_path, name):
        """Missing or unsupported extensions raise ValueError."""
        (firmware_file := tmp_path / name).touch()
        with pytest.raises(ValueError, match='has unrecognized extension'):
            tycmd._parse_firmware_file(firmware_file)


class TestReStripTag:
    @pytest.mark.parametrize(
        ('line', 'expected'),
        [
            # task messages, prefixed with '<task>@<board tag>' right-aligned to 28
            # chars
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
    def test_re_strip_tag(self, line, expected):
        """The task/board tag is stripped from task messages, other lines are kept."""
        assert tycmd._RE_STRIP_TAG.sub('', line) == expected

    def test_re_strip_tag_multiline(self):
        """The tag is stripped from every line of multi-line output."""
        output = (
            "       reset@11383920-Teensy  Resetting board '11383920-Teensy' "
            '(Teensy 3.1)\n'
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


class TestTycmdError:
    def test_tycmd_error_message(self):
        """The message is tycmd's error message."""
        error = tycmd.TycmdError(1, ['tycmd', 'reset'], stderr="Board 'nope' not found")
        assert str(error) == "Board 'nope' not found"

    def test_tycmd_error_message_without_stderr(self):
        """Without an error message, the message is the exit status."""
        for stderr in (None, ''):
            error = tycmd.TycmdError(1, ['tycmd', 'reset'], stderr=stderr)
            assert str(error) == str(CalledProcessError(1, ['tycmd', 'reset']))


class TestCallTycmd:
    def test_call_tycmd(self, mock_popen):
        """Only a non-zero exit code raises TycmdError, which carries tycmd's output."""
        # stderr alone doesn't make a call fail
        mock_popen.set_pipes(['status'], ['warning!'])
        assert tycmd._call_tycmd(['reset']) == 'status'

        # a non-zero exit code does
        mock_popen.set_pipes(['status'], ['error!'])
        mock_popen.set_returncode(-1)
        with pytest.raises(tycmd.TycmdError) as exc_info:
            tycmd._call_tycmd(['reset'])
        assert isinstance(exc_info.value, CalledProcessError)
        assert str(exc_info.value) == 'error!'
        assert exc_info.value.returncode == -1
        assert exc_info.value.output == 'status'
        assert exc_info.value.stderr == 'error!'

    def test_call_tycmd_strips_tags(self, mock_popen, caplog):
        """Tags are stripped from every line of stdout, stderr and log messages."""
        stdout = [
            (
                "       reset@11383920-Teensy  Resetting board '11383920-Teensy' "
                '(Teensy 3.1)'
            ),
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
            with pytest.raises(tycmd.TycmdError) as exc_info:
                tycmd._call_tycmd([], log_level=log_level)
            assert exc_info.value.stderr == 'First error\nSecond error'

    def test_call_tycmd_decoding(self):
        """Output is decoded as UTF-8, with invalid bytes replaced."""
        # run a real subprocess (Python standing in for tycmd) that writes UTF-8 plus a
        # byte that isn't valid UTF-8 to both stdout and stderr, then fails - so the
        # resulting TycmdError carries both decoded streams. -I -S skip site-packages
        # (and any slow .pth files in it), as the script only needs sys.
        script = (
            'import sys; '
            "sys.stdout.buffer.write(b'caf\\xc3\\xa9 M\\xfcller\\n'); "
            "sys.stderr.buffer.write(b'caf\\xc3\\xa9 M\\xfcller\\n'); "
            'sys.exit(1)'
        )
        with (
            patch('tycmd._resolve_tycmd', return_value=sys.executable),
            pytest.raises(tycmd.TycmdError) as exc_info,
        ):
            tycmd._call_tycmd([*PYTHON_ARGS, script])
        assert exc_info.value.output == 'café M\ufffdller'
        assert exc_info.value.stderr == 'café M\ufffdller'
        assert exc_info.value.cmd == [sys.executable, *PYTHON_ARGS, script]

    def test_call_tycmd_output_is_independent_of_log_level(self, mock_popen, caplog):
        """The returned output is the same regardless of log_level."""
        # real `tycmd list -O json -v` output, one JSON element per line
        stdout = [
            '[',
            (
                '  {"action": "add", "tag": "11383920-Teensy", "model": "Teensy 3.1", '
                '"location": "usb-3-2", "capabilities": ["run"], "interfaces": []}'
            ),
            ']',
        ]
        mock_popen.set_pipes(stdout, [])
        caplog.set_level(logging.DEBUG)

        outputs = [
            tycmd._call_tycmd([], log_level=x) for x in (logging.NOTSET, logging.INFO)
        ]
        assert outputs[0] == outputs[1] == '\n'.join(line.strip() for line in stdout)

        boards = tycmd.list_boards()
        assert boards[0]['tag'] == '11383920-Teensy'

    def test_call_tycmd_logging(self, mock_popen, caplog):
        """stdout is logged at log_level, stderr always at WARNING, empty lines never."""
        caplog.set_level(logging.DEBUG)

        def records():
            # sorted, as stdout and stderr are logged from different threads, so the
            # order between the two streams isn't deterministic
            return sorted(
                (r.levelno, r.getMessage())
                for r in caplog.records
                if r.levelno > logging.DEBUG
            )

        # stdout is logged at log_level, without empty lines; stderr of a successful
        # call is logged as a warning
        mock_popen.set_pipes(
            ['       reset@11383920-Teensy  Sending reset command', '', '   '],
            ['       reset@11383920-Teensy  Some warning', ''],
        )
        tycmd._call_tycmd([], log_level=logging.INFO)
        assert records() == [
            (logging.INFO, 'Sending reset command'),
            (logging.WARNING, 'Some warning'),
        ]

        # log_level only applies to stdout - warnings are always logged at WARNING
        for log_level in (logging.NOTSET, logging.ERROR):
            caplog.clear()
            tycmd._call_tycmd([], log_level=log_level)
            expected = [(logging.WARNING, 'Some warning')]
            if log_level > logging.NOTSET:
                expected.append((log_level, 'Sending reset command'))
            assert records() == expected

        # stderr is logged live, before it is known whether the call fails - so stderr
        # of a failing call has been logged as well
        caplog.clear()
        mock_popen.set_returncode(1)
        with pytest.raises(tycmd.TycmdError) as exc_info:
            tycmd._call_tycmd([])
        assert exc_info.value.stderr == 'Some warning'
        assert records() == [(logging.WARNING, 'Some warning')]

    @pytest.mark.parametrize('log_level', [logging.NOTSET, logging.INFO, logging.ERROR])
    def test_call_tycmd_logs_user_action_as_warning(
        self, mock_popen, caplog, log_level
    ):
        """Requests to press the board's button are always logged at WARNING."""
        # tycmd prints these at its INFO level (stdout) and then waits indefinitely, so
        # they must never be hidden by log_level
        mock_popen.set_pipes(
            [
                "upload@11383920-Teensy  Reboot didn't work, press button manually",
                'upload@11383920-Teensy  Waiting for device (press button to reboot)...',
            ],
            [],
        )
        caplog.set_level(logging.DEBUG)
        tycmd._call_tycmd([], log_level=log_level)
        assert [(r.levelno, r.getMessage()) for r in caplog.records[1:]] == [
            (logging.WARNING, "Reboot didn't work, press button manually"),
            (logging.WARNING, 'Waiting for device (press button to reboot)...'),
        ]

    def test_call_tycmd_kills_tycmd_on_error(self):
        """An error while reading the output kills tycmd instead of waiting for it."""
        # a child that doesn't exit on its own, like tycmd waiting for a button press
        script = "import time; print('waiting', flush=True); time.sleep(60)"
        threads_before = threading.active_count()
        start = time.monotonic()
        with (
            patch('tycmd._resolve_tycmd', return_value=sys.executable),
            patch.object(tycmd.log, 'log', side_effect=RuntimeError('handler failed')),
            pytest.raises(RuntimeError, match='handler failed'),
        ):
            tycmd._call_tycmd([*PYTHON_ARGS, script], log_level=logging.INFO)

        # the error surfaces right away instead of after the child exits, and the
        # stderr thread has been joined
        assert time.monotonic() - start < 30
        assert threading.active_count() == threads_before


class TestAssembleArgs:
    def test_assemble_args(self):
        """The board filter is assembled into a single --board argument."""
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


def _record_entry(path: Path) -> SimpleNamespace:
    # stand-in for an importlib.metadata.PackagePath from the package's RECORD
    return SimpleNamespace(name=path.name, locate=lambda: path)


class TestResolveTycmd:
    def test_resolve_tycmd(self):
        """The bundled binary is found in the installed package's RECORD."""
        path = Path(tycmd._resolve_tycmd())
        assert path.is_file()
        assert path.name == tycmd._TYCMD_NAME

    def test_resolve_tycmd_record(self, tmp_path):
        """The binary's RECORD entry is resolved to an absolute path."""
        binary = tmp_path / 'bin' / tycmd._TYCMD_NAME
        binary.parent.mkdir()
        binary.touch()
        record = [
            _record_entry(tmp_path / 'site-packages' / 'tycmd' / '__init__.py'),
            _record_entry(binary),
        ]
        with patch('tycmd.files', return_value=record):
            assert tycmd._resolve_tycmd() == str(binary.resolve())

    @pytest.mark.parametrize(
        'files_kwargs',
        [
            {'side_effect': tycmd.PackageNotFoundError('tycmd-wrapper')},
            {'return_value': None},
            {'return_value': [_record_entry(Path('tycmd', '__init__.py'))]},
            {'return_value': [_record_entry(Path('does', 'not', 'exist', 'tycmd'))]},
        ],
    )
    def test_resolve_tycmd_not_found(self, files_kwargs):
        """A missing binary raises FileNotFoundError instead of falling back to PATH."""
        with (
            patch('tycmd.files', **files_kwargs),
            patch('tycmd._TYCMD_NAME', 'tycmd'),
            pytest.raises(FileNotFoundError, match='bundled with tycmd-wrapper'),
        ):
            tycmd._resolve_tycmd()
