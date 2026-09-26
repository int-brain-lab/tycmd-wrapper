import re
import shutil
import subprocess
from pathlib import Path
from platform import machine, system
from tempfile import TemporaryDirectory

from pdm.backend.hooks import Context

REPO_URL = 'https://github.com/Koromix/rygel'


def _tycmd_version() -> str:
    content = Path(__file__).parent.joinpath('tycmd.py').read_text()
    match = re.search(r"_TYCMD_VERSION = ['\"]([^'\"]+)['\"]", content)
    if match is None:
        raise RuntimeError('Could not find _TYCMD_VERSION in tycmd.py')
    return match.group(1)


def _check_version(binary: Path, version: str) -> None:
    result = subprocess.check_output([str(binary), '--version'], text=True, timeout=5)
    if version not in result:
        raise RuntimeError(
            f'{binary} reports unexpected version: {result.strip()!r} (expected {version!r})'
        )


def build_tycmd(output_dir: Path) -> Path:
    """Clone tycmd source at the pinned version and build it via felix into `output_dir`."""
    is_windows = system() == 'Windows'
    version = _tycmd_version()
    print(f'Building tycmd {version} for {system()} {machine()}...')

    # check if git executable is available
    if shutil.which('git') is None:
        raise RuntimeError('Could not find git executable')

    output_dir = output_dir.resolve()

    with TemporaryDirectory() as tmp:
        # find tag
        src = Path(tmp, 'rygel')
        try:
            result = subprocess.check_output(['git', 'ls-remote', '--tags', REPO_URL, 'tytools*'], text=True, cwd=tmp)
            tags = [ref.split("\t", 1)[1].removeprefix("refs/tags/") for ref in result.splitlines()]
            tag = next(t for t in tags if 'tytools/' in t and t.endswith(f'/{version}'))
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Could not list git tags for {REPO_URL}') from e
        except StopIteration as e:
            raise RuntimeError(f'Could not find git tag matching tycmd {version} in {REPO_URL}') from e

        # clone rygel
        try:
            subprocess.check_call(['git', 'clone', '--depth', '1', '--branch', tag, REPO_URL, str(src)], cwd=tmp)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Could not clone rygel') from e

        # build tycmd
        try:
            bootstrap = src / ('bootstrap.bat' if is_windows else 'bootstrap.sh')
            felix = src / ('felix.exe' if is_windows else 'felix')
            subprocess.check_call([str(bootstrap)], cwd=src, shell=is_windows)
            subprocess.check_call([str(felix), '-pFast', '-O', str(output_dir), 'tycmd'], cwd=src)
            binary = next(output_dir.glob('tycmd*')).resolve()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Could not build tycmd {version}') from e
        except StopIteration as e:
            raise RuntimeError(f'Cannot find built tycmd binary in {output_dir}') from e

    # check & return binary
    _check_version(binary, version)
    return binary


def _ensure_tycmd(output_dir: Path) -> Path:
    """Return a working tycmd binary in `output_dir` matching the pinned version."""
    version = _tycmd_version()
    existing = next(output_dir.glob('tycmd*'), None)
    if existing is not None:
        try:
            _check_version(existing, version)
            return existing
        except Exception:
            print(f'{existing} is stale or broken, rebuilding...')
    return build_tycmd(output_dir)


def pdm_build_initialize(context: Context):
    if context.target == 'sdist':
        return
    context.config_settings['--python-tag'] = 'py3'
    context.config_settings['--py-limited-api'] = 'none'

    match system(), machine():
        case "Windows", "AMD64":
            pass
        case "Darwin", "x86_64" | "arm64":
            context.config_settings['--plat-name'] = f'macosx_11_0_{machine()}'
        case "Linux", "x86_64" | "aarch64":
            pass
        case _:
            raise NotImplementedError(f"Unsupported platform: {system()} {machine()}")

    output_dir = Path(__file__).parent / 'bin'
    tycmd = _ensure_tycmd(output_dir)

    wheel_data = context.config.build_config.get("wheel-data", dict())
    wheel_data["scripts"] = [
        {
            "path": str(tycmd.relative_to(Path(__file__).parent)),
            "relative-to": str(tycmd.parent),
        }
    ]
    context.config.build_config["wheel-data"] = wheel_data

if __name__ == '__main__':
    _ensure_tycmd(Path('bin'))
