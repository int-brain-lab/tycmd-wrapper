import tycmd
import re


def test_version():
    output = tycmd.version(full=True)
    assert isinstance(output, str)
    match = re.search(r"^.+(\d+\.\d+\.\d+)", output)
    assert match is not None
    assert match.groups()[0] == tycmd._TYCMD_VERSION
    assert tycmd.version(full=False) == tycmd._TYCMD_VERSION


def test__assemble_tag():
    output = tycmd._assemble_tag(serial='serial')
    assert output == ['-B', 'serial']
    output = tycmd._assemble_tag(family='family')
    assert output == ['-B', '-family']
    output = tycmd._assemble_tag(port='port')
    assert output == ['-B', '@port']
    output = tycmd._assemble_tag(serial='serial', family='family', port='port')
    assert output == ['-B', 'serial-family@port']
    output = tycmd._assemble_tag()
    assert output == []
