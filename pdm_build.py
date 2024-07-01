import re
from pathlib import Path
from platform import system, architecture

from pdm.backend.hooks import Context


def pdm_build_initialize(context: Context):
    src_includes = context.config.build_config.get("source-includes", [])

    if context.target == "wheel":
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
        src_includes += [str(tycmd)]
    else:
        src_includes += [str(Path("bin", "*", "tycmd*"))]

    context.config.build_config["source-includes"] = src_includes


def pdm_build_finalize(context: Context, artifact: Path):
    if artifact.suffix == '.whl':
        match system():
            case "Linux" if "64bit" in architecture():
                platform = 'linux_x86_64'
            case "Windows" if "64bit" in architecture():
                platform = 'win_amd64'
            case "Darwin":
                platform = 'macosx_10_9_x86_64'
        pattern = r'(^\w+-[\d\.]+)-.*'
        new_name = re.sub(pattern, fr'\1-py3-none-{platform}.whl', str(artifact.name))
        artifact.rename(artifact.with_name(new_name))
