# -*- coding: utf-8 -*-

"""Tests of the gPhoto2 logging callback."""

import unittest

from pibooth.camera.gphoto import gp_log_callback


class LogCallbackTest(unittest.TestCase):

    def _logged(self, domain, string):
        with self.assertLogs('pibooth.gphoto2', 'DEBUG') as logs:
            gp_log_callback(0, domain, string)
        return logs.records[0].getMessage()

    def test_bytes_from_python_gphoto2_before_2_5(self):
        self.assertEqual(self._logged(b'gphoto2-camera', b'Initializing'), 'gphoto2-camera: Initializing')

    def test_str_from_python_gphoto2_2_5(self):
        self.assertEqual(self._logged('gphoto2-camera', 'Initializing'), 'gphoto2-camera: Initializing')


if __name__ == '__main__':
    unittest.main()
