import re
from pathlib import Path
from platform import system, architecture

from pdm.backend.hooks import Context


def pdm_build_hook_enabled(context: Context):
    return context.target == "wheel"


def pdm_build_initialize(context: Context):
    match system():
        case "Linux" if "64bit" in architecture():
            tycmd = Path("bin", "linux64", "tycmd")
        case "Windows" if "64bit" in architecture():
            tycmd = Path("bin", "win64", "tycmd.exe")
        case "Darwin":
            tycmd = Path("bin", "osx", "tycmd")
        case _:
            raise NotImplementedError()
    assert tycmd.exists()
    wheel_data = context.config.build_config.get("wheel-data", dict())
    wheel_data["scripts"] = [{"path": str(tycmd), "relative-to": str(tycmd.parent)}]
    context.config.build_config["wheel-data"] = wheel_data


def pdm_build_finalize(context: Context, artifact: Path):
    pattern = r"(^[^-]+)-([^-]+)-([^-]+)-([^-]+)-([^-\.]+)"
    name_tag, version_tag, python_tag, abi_tag, platform_tag = re.match(
        pattern, artifact.name
    ).groups()
    python_tag = 'py3'
    abi_tag = 'none'
    match system():
        case "Linux" if "64bit" in architecture():
            pass
        case "Windows" if "64bit" in architecture():
            platform_tag = 'win_amd64'
        case "Darwin":
            platform_tag = 'macosx_10_9_x86_64'
        case _:
            raise NotImplementedError()
    new_name = f'{name_tag}-{version_tag}-{python_tag}-{abi_tag}-{platform_tag}.whl'
    artifact.rename(artifact.with_name(new_name))
