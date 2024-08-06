tycmd-wrapper
=============

A Python wrapper for [tycmd](https://koromix.dev/tytools) by 
[Niels Martignène](https://github.com/Koromix/) - a tool for managing 
[Teensy USB Development Boards](https://www.pjrc.com/teensy/) by PJRC.


Examples
--------

### Identifying a firmware file

To identify which models are compatible with a specific firmware file, use the identify function.

```python
import tycmd
compatible_models = tycmd.identify('blink.hex')
```

Models compatible with the firmware file will be returned as a list of strings:
```python
['Teensy 4.0', 'Teensy 4.0 (beta 1)']
```

### List Available Boards
To list all available boards, use the list_boards function.

```python
import tycmd
boards = list_boards()
```

Details for the available boards will be returned as a list of python dictionaries.
```python
[
    {
        'action': 'add',
        'tag': '3576040-Teensy',
        'serial': '3576040',
        'description': 'USB Serial',
        'model': 'Teensy 3.1',
        'location': 'usb-1-4',
        'capabilities': ['unique', 'run', 'reboot', 'serial'],
        'interfaces': [['Serial', '/dev/ttyACM1']],
    },
    {
        'action': 'add',
        'tag': '14014980-Teensy',
        'serial': '14014980',
        'description': 'USB Serial',
        'model': 'Teensy 4.0',
        'location': 'usb-1-3',
        'capabilities': ['unique', 'run', 'rtc', 'reboot', 'serial'],
        'interfaces': [['Serial', '/dev/ttyACM0']],
    },
]
```

### Uploading a firmware file

To upload firmware to a board, use the `upload` function.
You can address a board by its port or by its serial number.

```python
import tycmd
import logging

logging.basicConfig(level=logging.INFO)
tycmd.upload('blink.hex', port='/dev/ttyACM0')
```

The upload progress will be logged:
```
INFO:tycmd:Uploading to board '14014980-Teensy' (Teensy 4.0)
INFO:tycmd:Triggering board reboot
INFO:tycmd:Firmware: blink40.hex
INFO:tycmd:Flash usage: 19 kiB (1.0%)
INFO:tycmd:Uploading...
INFO:tycmd:Sending reset command (with RTC)
```

Full Documentation
------------------

The full API documentation is available [here](https://int-brain-lab.github.io/tycmd-wrapper).

![License](https://img.shields.io/github/license/int-brain-lab/tycmd-wrapper)
[![Coverage](https://img.shields.io/coverallsCoverage/github/int-brain-lab/tycmd-wrapper)](https://coveralls.io/github/int-brain-lab/tycmd-wrapper)
[![CI](https://github.com/int-brain-lab/tycmd-wrapper/actions/workflows/testing.yaml/badge.svg)](https://github.com/int-brain-lab/tycmd-wrapper/actions)
[![PyPI](https://img.shields.io/pypi/v/tycmd-wrapper)](https://pypi.org/project/tycmd-wrapper/)
