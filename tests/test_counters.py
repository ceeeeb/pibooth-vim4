# -*- coding: utf-8 -*-

"""Tests of the counters persisted in a JSON file."""

import os
import json
import pickle
import shutil
import tempfile
import unittest
import os.path as osp

from pibooth.counters import Counters


class CountersTest(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.filename = osp.join(self.directory, 'counters.json')
        self.legacy_filename = osp.join(self.directory, 'counters.pickle')

    def tearDown(self):
        shutil.rmtree(self.directory)

    def _counters(self):
        return Counters(self.filename, taken=0, printed=0)

    def _saved_data(self):
        with open(self.filename, 'r', encoding='utf-8') as fp:
            return json.load(fp)

    def _write(self, filename, content):
        with open(filename, 'wb') as fp:
            fp.write(content)

    def test_set_saves_in_json(self):
        counters = self._counters()
        counters.taken += 3
        self.assertEqual(self._saved_data(), {'taken': 3, 'printed': 0})

    def test_values_are_reloaded(self):
        self._counters().printed = 5
        self.assertEqual(self._counters().printed, 5)

    def test_reset(self):
        counters = self._counters()
        counters.taken = 5
        counters.reset()
        self.assertEqual(self._saved_data(), {'taken': 0, 'printed': 0})

    def test_unknown_counter(self):
        with self.assertRaises(AttributeError):
            self._counters().unknown

    def test_no_temporary_file_left(self):
        self._counters().taken = 1
        self.assertEqual(os.listdir(self.directory), ['counters.json'])

    def test_pickle_is_migrated(self):
        self._write(self.legacy_filename, pickle.dumps({'taken': 42, 'printed': 7}))
        counters = self._counters()
        self.assertEqual((counters.taken, counters.printed), (42, 7))
        self.assertEqual(self._saved_data(), {'taken': 42, 'printed': 7})

    def test_json_takes_precedence_over_pickle(self):
        self._write(self.legacy_filename, pickle.dumps({'taken': 42}))
        self._counters()
        self._write(self.legacy_filename, pickle.dumps({'taken': 1000}))
        self.assertEqual(self._counters().taken, 42)

    def test_corrupted_pickle_resets(self):
        self._write(self.legacy_filename, b'\x80\x05 garbage')
        self.assertEqual(self._counters().taken, 0)
        self.assertEqual(self._saved_data(), {'taken': 0, 'printed': 0})

    def test_corrupted_json_resets(self):
        for content in (b'{"taken": 3', b'', b'[1, 2]', b'"taken"', b'\xff\xfe'):
            with self.subTest(content=content):
                self._write(self.filename, content)
                self.assertEqual(self._counters().taken, 0)
                self.assertEqual(self._saved_data(), {'taken': 0, 'printed': 0})


if __name__ == '__main__':
    unittest.main()
