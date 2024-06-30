import warnings

import tycmd
import re


def test_version():
    output = tycmd.version(full=True)
    assert isinstance(output, str)
    warnings.warn(output)
    match = re.search(r"^.+(\d+\.\d+\.\d+).+$", output)
    assert match is not None
    assert match.groups()[0] == tycmd._TYCMD_VERSION
    assert tycmd.version(full=False) == tycmd._TYCMD_VERSION
