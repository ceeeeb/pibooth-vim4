# -*- coding: utf-8 -*-

"""Script to check the buttons and LEDs wiring of the photo booth.
"""

import time

from pibooth import hardware
from pibooth.hardware.base import GpioError
from pibooth.utils import configure_logging
from pibooth.config import PiConfigParser
from pibooth.plugins import create_plugin_manager

# Duration of the buttons watching sequence
WATCH_TIME = 20


def get_configured_pins(config, suffix):
    """Yield the (option, pin) declared in the CONTROLS section and matching the
    given suffix. A pin set to 0 means that the device is not wired.
    """
    for option in config.options('CONTROLS'):
        if option.endswith(suffix):
            pin = config.getint('CONTROLS', option)
            if pin:
                yield option, pin


def create_devices(config, suffix, factory):
    """Return the devices declared in the configuration, skipping the ones which
    can not be created on this board.
    """
    devices = {}
    for option, pin in get_configured_pins(config, suffix):
        try:
            devices[option] = factory(pin)
            print(" -> {:.<25} pin {:>2} : OK".format(option, pin))
        except GpioError as ex:
            print(" -> {:.<25} pin {:>2} : {}".format(option, pin, ex))
    return devices


def check_leds(leds):
    """Light up each LED one after the other."""
    if not leds:
        return
    print("\nLighting up each LED for 2 seconds:\n")
    for name, led in leds.items():
        print(" -> {}".format(name))
        led.blink(on_time=0.2, off_time=0.2)
        time.sleep(2)
        led.off()


def check_buttons(buttons):
    """Report the buttons state changes."""
    if not buttons:
        return
    print("\nPress the buttons, {} seconds to go (Ctrl-C to stop):\n".format(WATCH_TIME))
    states = {name: button.value for name, button in buttons.items()}
    end = time.time() + WATCH_TIME
    while time.time() < end:
        for name, button in buttons.items():
            if button.value != states[name]:
                states[name] = button.value
                print(" -> {:.<25} {}".format(name, 'PRESSED' if states[name] else 'released'))
        time.sleep(0.02)


def main():
    """Application entry point.
    """
    configure_logging()
    plugin_manager = create_plugin_manager()
    config = PiConfigParser("~/.config/pibooth/pibooth.cfg", plugin_manager)

    board = hardware.find_board()
    print("\nBoard detected: {}\n".format(board.name))

    hold_time = config.getfloat('CONTROLS', 'debounce_delay')
    print("Claiming the GPIO lines declared in the configuration:\n")
    leds = create_devices(config, '_led_pin', board.create_led)
    buttons = create_devices(config, '_btn_pin',
                             lambda pin: board.create_button(pin, hold_time))

    try:
        check_leds(leds)
        check_buttons(buttons)
    except KeyboardInterrupt:
        pass
    finally:
        for device in list(leds.values()) + list(buttons.values()):
            device.close()
    print()


if __name__ == "__main__":
    main()
