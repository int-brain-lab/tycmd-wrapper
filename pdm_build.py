"""pdm-backend build hook that bundles the tycmd binary with the wheel."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from platform import libc_ver, machine, system
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdm.backend.hooks import Context  # Only needed for the type annotation

REPO_URL = 'https://github.com/Koromix/rygel'
TYCMD_NAME = 'tycmd.exe' if system() == 'Windows' else 'tycmd'
STAMP_NAME = 'tycmd.build'
"""Next to the binary, records what it was built from - see _build_stamp()."""
MACOS_DEPLOYMENT_TARGET = '11.0'
FELIX_ARGS = ['-pFast', 'tycmd']
"""Arguments for felix, rygel's build tool, to build tycmd."""


def _read_constant(name: str) -> str:
    content = Path(__file__).parent.joinpath('tycmd', '__init__.py').read_text()
    match = re.search(
        rf"^{re.escape(name)} = ['\"]([^'\"]+)['\"]", content, re.MULTILINE
    )
    if match is None:
        raise RuntimeError(f'Could not find {name} in tycmd/__init__.py')
    return match.group(1)


def _tycmd_version() -> str:
    return _read_constant('_TYCMD_VERSION')


def _tycmd_commit() -> str:
    return _read_constant('_TYCMD_COMMIT')


def _check_version(binary: Path, version: str) -> None:
    result = subprocess.check_output([str(binary), '--version'], text=True, timeout=30)
    if version not in result.split():
        raise RuntimeError(
            f'{binary} reports unexpected version: {result.strip()!r} (expected {version!r})'
        )


def build_tycmd(output_dir: Path) -> Path:
    """Clone tycmd source at the pinned version and build it via felix into `output_dir`."""
    is_windows = system() == 'Windows'
    version = _tycmd_version()
    commit = _tycmd_commit()
    print(f'Building tycmd {version} for {system()} {machine()}...')

    # check if git executable is available
    if shutil.which('git') is None:
        raise RuntimeError('Could not find git executable')

    output_dir = output_dir.resolve()

    with TemporaryDirectory() as tmp:
        # clone rygel - its tytools release tags are named tytools/<version>
        src = Path(tmp, 'rygel')
        tag = f'tytools/{version}'
        clone = ['git', 'clone', '--depth=1', f'--branch={tag}', REPO_URL, str(src)]
        try:
            subprocess.check_call(clone, cwd=tmp)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Could not clone rygel {tag}') from e

        # make sure the tag still points to the pinned commit. --git-dir, as an inherited
        # GIT_DIR (e.g. in git hooks) would otherwise point git at another repository.
        cloned = subprocess.check_output(
            ['git', f'--git-dir={src / ".git"}', 'rev-parse', 'HEAD'], text=True
        ).strip()
        if cloned != commit:
            raise RuntimeError(
                f'rygel {tag} is commit {cloned}, but {commit} is pinned'
            )

        # build tycmd
        try:
            bootstrap = src / ('bootstrap.bat' if is_windows else 'bootstrap.sh')
            felix = src / ('felix.exe' if is_windows else 'felix')
            subprocess.check_call([str(bootstrap)], cwd=src, shell=is_windows)
            build_env = os.environ.copy()
            if system() == 'Darwin':
                build_env['MACOSX_DEPLOYMENT_TARGET'] = MACOS_DEPLOYMENT_TARGET
            subprocess.check_call([str(felix), *FELIX_ARGS], cwd=src, env=build_env)
            built = next(src.joinpath('bin').rglob(TYCMD_NAME))
        except StopIteration as e:
            raise FileNotFoundError('Could not find built tycmd binary') from e
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Could not build tycmd {version}') from e

        output_dir.mkdir(parents=True, exist_ok=True)
        binary = Path(shutil.copy2(built, output_dir / built.name))
        if not is_windows:
            binary.chmod(0o755)

    # check & return binary
    _check_version(binary, version)
    output_dir.joinpath(STAMP_NAME).write_text(_build_stamp(commit))
    return binary


def _build_stamp(commit: str) -> str:
    """Return what a binary is built from - a change in it calls for a rebuild."""
    stamp: dict[str, object] = {'commit': commit, 'felix': FELIX_ARGS}
    if system() == 'Darwin':
        stamp['macos'] = MACOS_DEPLOYMENT_TARGET
    return json.dumps(stamp)


def _ensure_tycmd(output_dir: Path) -> Path:
    """Return a working tycmd binary in `output_dir`, built as currently configured."""
    version = _tycmd_version()
    stamp = _build_stamp(_tycmd_commit())
    existing = output_dir / TYCMD_NAME
    if existing.exists():
        if system() != 'Windows':
            existing.chmod(0o755)
        try:
            if output_dir.joinpath(STAMP_NAME).read_text() != stamp:
                raise RuntimeError('built with a different configuration')
            _check_version(existing, version)
            return existing
        except (OSError, subprocess.SubprocessError, RuntimeError) as e:
            print(f'{existing} is stale or broken ({e!r}), rebuilding...')
    return build_tycmd(output_dir)


def pdm_build_initialize(context: Context) -> None:
    """Set the wheel's tags and add the tycmd binary to its scripts."""
    if context.target == 'sdist':
        return
    context.config_settings['--python-tag'] = 'py3'
    context.config_settings['--py-limited-api'] = 'none'

    if system() == 'Darwin':
        plat_version = MACOS_DEPLOYMENT_TARGET.replace('.', '_')
        context.config_settings['--plat-name'] = f'macosx_{plat_version}_{machine()}'
    elif system() == 'Linux' and (libc := libc_ver())[0] == 'glibc':
        glibc_major, glibc_minor = libc[1].split('.')[:2]
        plat_name = f'manylinux_{glibc_major}_{glibc_minor}_{machine()}'
        context.config_settings['--plat-name'] = plat_name

    output_dir = Path(__file__).parent / 'bin'
    tycmd = _ensure_tycmd(output_dir)

    wheel_data = context.config.build_config.get('wheel-data', {})
    wheel_data['scripts'] = [
        {
            'path': str(tycmd.relative_to(Path(__file__).parent)),
            'relative-to': str(tycmd.parent),
        }
    ]
    context.config.build_config['wheel-data'] = wheel_data


if __name__ == '__main__':
    _ensure_tycmd(Path('bin'))
