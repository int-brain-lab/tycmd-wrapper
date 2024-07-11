from pathlib import Path
from platform import system, architecture

from pdm.backend.hooks import Context


def pdm_build_initialize(context: Context):
    context.config_settings['--python-tag'] = 'py3'
    context.config_settings['--py-limited-api'] = 'none'
    wheel_data = context.config.build_config.get("wheel-data", dict())
    match system():
        case "Linux" if "64bit" in architecture():
            tycmd = Path("bin", "linux64", "tycmd")
        case "Windows" if "64bit" in architecture():
            tycmd = Path("bin", "win64", "tycmd.exe")
            context.config_settings['--plat-name'] = 'win_amd64'
        case "Darwin":
            tycmd = Path("bin", "osx", "tycmd")
            context.config_settings['--plat-name'] = 'macosx_10_9_x86_64'
        case _:
            raise NotImplementedError()
    assert tycmd.exists()
    wheel_data["scripts"] = [{"path": str(tycmd), "relative-to": str(tycmd.parent)}]
    context.config.build_config["wheel-data"] = wheel_data
