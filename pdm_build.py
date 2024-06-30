from pathlib import Path
from platform import system, architecture

from pdm.backend.hooks import Context


def pdm_build_initialize(context: Context):
    match system():
        case "Linux" if "64bit" in architecture():
            tycmd = Path("bin", "linux64", "tycmd")
        case "Windows":
            tycmd = Path("bin", "win64", "tycmd.exe")
        case "Darwin":
            tycmd = Path("bin", "osx", "tycmd")
        case _:
            raise NotImplementedError()
    assert tycmd.exists()

    src_includes = context.config.build_config.get("source-includes", [])
    wheel_data = context.config.build_config.get("wheel-data", dict())
    wheel_data["scripts"] = [{"path": str(tycmd), "relative-to": str(tycmd.parent)}]

    context.config.build_config["source-includes"] = src_includes + [str(tycmd)]
    context.config.build_config["wheel-data"] = wheel_data
