# -*- coding: utf-8 -*-

"""Trajectory of a picture flying across the screen, used to show that a
picture goes to the printer queue.
"""


def ease_in_out(progress):
    """Return the eased progress: slow start, fast middle, slow end.

    :param progress: linear progress between 0 and 1
    :type progress: float
    """
    return progress * progress * (3 - 2 * progress)


def flight_point(start, end, arc_height, progress):
    """Return the point reached at the given progress on an arc from start
    to end, rising arc_height pixels above the highest of both points.

    :param start: (x, y) start point
    :type start: tuple
    :param end: (x, y) end point
    :type end: tuple
    :param arc_height: height of the arc in pixels
    :type arc_height: float
    :param progress: linear progress between 0 and 1
    :type progress: float
    """
    t = ease_in_out(progress)
    control = ((start[0] + end[0]) / 2, min(start[1], end[1]) - arc_height)
    return tuple((1 - t) ** 2 * start[i] + 2 * (1 - t) * t * control[i] + t ** 2 * end[i] for i in (0, 1))


def flight_scale(start_side, end_side, progress):
    """Return the scale to apply to a picture whose largest side goes from
    start_side to end_side during the flight.
    """
    return 1 + (end_side / start_side - 1) * ease_in_out(progress)
