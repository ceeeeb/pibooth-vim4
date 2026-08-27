# -*- coding: utf-8 -*-

"""Board independent access to the buttons and LEDs of the photo booth.

The board running pibooth is detected at startup and the matching GPIO backend
is loaded, so that the pin numbers written in ``pibooth.cfg`` always are the
physical numbers of the 40 pins header, whatever the board.
"""

import os
import configparser
from importlib import import_module

from pibooth.utils import LOGGER
from pibooth.hardware.base import GpioError

DEVICE_TREE_MODEL = '/proc/device-tree/model'

PINOUTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pinouts.ini')

BACKENDS = {'gpiozero': 'pibooth.hardware.rpi',
            'chardev': 'pibooth.hardware.chardev',
            'mock': 'pibooth.hardware.mock'}


def get_board_model():
    """Return the board model published by the kernel, an empty string if the
    machine has no device tree (a regular PC for instance).
    """
    try:
        with open(DEVICE_TREE_MODEL, 'rb') as fp:
            return fp.read().decode('utf-8').replace('\x00', '').strip()
    except IOError:
        return ''


class Board(object):

    """The GPIO capabilities of the machine running pibooth.

    :param name: human readable name of the board
    :param backend: module implementing the Button and Led classes
    :param lines: mapping between header pin numbers and kernel GPIO lines,
                  empty when the backend addresses the pins by header number
    """

    def __init__(self, name, backend, lines=None):
        self.name = name
        self._backend = backend
        self._lines = lines or {}

    def _line(self, pin):
        if not self._lines:
            return pin
        try:
            return self._lines[int(pin)]
        except KeyError:
            raise GpioError("Pin {} of the {} is not available as GPIO, usable pins are: {}".format(
                pin, self.name, ', '.join(str(p) for p in sorted(self._lines))))

    def create_button(self, pin, hold_time=0.2, pull_up=True):
        """Return a button connected to the given header pin."""
        return self._backend.Button(self._line(pin), pull_up=pull_up, hold_time=hold_time)

    def create_led(self, pin):
        """Return a LED connected to the given header pin."""
        return self._backend.Led(self._line(pin))


def find_board():
    """Return the :py:class:`Board` matching the running machine."""
    model = get_board_model()
    parser = configparser.ConfigParser()
    parser.read(PINOUTS_FILE)

    for section in parser.sections():
        if model and parser.get(section, 'detect') in model:
            backend = import_module(BACKENDS[parser.get(section, 'backend')])
            lines = {int(pin): line for pin, line in parser.items(section) if pin.isdigit()}
            LOGGER.info("Board '%s' detected, GPIO handled by the '%s' backend",
                        model, parser.get(section, 'backend'))
            return Board(model, backend, lines)

    LOGGER.warning("Board '%s' is not declared in %s, fallback to GPIO mock",
                   model or 'unknown', PINOUTS_FILE)
    return Board(model or 'unknown board', import_module(BACKENDS['mock']))


class DeviceGroup(object):

    """A set of GPIO devices addressed by name."""

    def __init__(self, **devices):
        self._devices = devices
        for name, device in devices.items():
            setattr(self, name, device)

    def __iter__(self):
        return iter(self._devices.values())

    def close(self):
        for device in self:
            device.close()


class ButtonGroup(DeviceGroup):

    """The push buttons of the photo booth."""

    @property
    def value(self):
        return tuple(button.value for button in self)


class LedGroup(DeviceGroup):

    """The LEDs of the photo booth, which can be driven all together."""

    def on(self):
        for led in self:
            led.on()

    def off(self):
        for led in self:
            led.off()

    def blink(self, on_time=1, off_time=1):
        for led in self:
            led.blink(on_time=on_time, off_time=off_time)
