# -*- coding: utf-8 -*-

"""Minimal access to the V4L2 controls that OpenCV does not expose.
"""

import os
import fcntl
import struct

# VIDIOC_S_CTRL = _IOWR('V', 28, struct v4l2_control)
VIDIOC_S_CTRL = 0xC008561C

CID_POWER_LINE_FREQUENCY = 0x00980918
CID_FOCUS_ABSOLUTE = 0x009A090A
CID_FOCUS_AUTO = 0x009A090C

# V4L2_CID_POWER_LINE_FREQUENCY menu entries
POWER_LINE_MENU = {50: 1, 60: 2}


def find_opened_device():
    """Return the path of the ``/dev/videoN`` device opened by this process,
    or None. OpenCV opens the device by index and does not tell which one.
    """
    for fd in os.listdir('/proc/self/fd'):
        try:
            target = os.readlink(os.path.join('/proc/self/fd', fd))
        except OSError:
            continue
        if target.startswith('/dev/video'):
            return target
    return None


def set_control(device, control_id, value):
    """Set a V4L2 control, raise OSError if the device refuses it.
    """
    with open(device, 'rb', buffering=0) as fp:
        fcntl.ioctl(fp, VIDIOC_S_CTRL, struct.pack('Ii', control_id, value))
