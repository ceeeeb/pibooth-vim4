# -*- coding: utf-8 -*-

import os
import json
import pickle
import os.path as osp

from pibooth.utils import LOGGER


class Counters(object):

    """Persistent counters stored in a JSON file. A ``.pickle`` file written
    by a previous version of pibooth, next to the JSON one, is migrated on
    first load.
    """

    def __init__(self, filename='', **kwargs):
        self.data = kwargs.copy()
        self.default = kwargs
        self.filename = osp.abspath(osp.expanduser(filename))
        self.legacy_filename = osp.splitext(self.filename)[0] + '.pickle'
        if osp.isfile(self.filename) or osp.isfile(self.legacy_filename):
            self.load()

    def __str__(self):
        return ", ".join("{}:{}".format(key, value) for key, value in self.data.items())

    def __iter__(self):
        """Iterate over counters names.
        """
        return iter(self.data)

    def __getitem__(self, name):
        """Get value from counter name.
        """
        return self.__getattr__(name)

    def __getattr__(self, name):
        """Called only when an attribute does not exist.
        """
        if name not in self.data:
            raise AttributeError("No counter with name '{}'".format(name))
        return self.data[name]

    def __setattr__(self, name, value):
        """Called each time an attribute is set.
        """
        if name != 'data' and name in self.data:
            self.data[name] = value
            self.save()
        else:
            super(Counters, self).__setattr__(name, value)

    def names(self):
        """Return the list of counters.
        """
        return [key for key in self.data]

    def load(self):
        """Load the saved counters, migrating the legacy pickle file if the
        JSON one does not exist yet. An unreadable file resets the counters
        instead of preventing the application from starting.
        """
        if osp.isfile(self.filename):
            source, reader = self.filename, self._read_json
        else:
            source, reader = self.legacy_filename, self._read_pickle

        try:
            self.data.update(reader())
        except Exception as ex:  # pickle can raise almost anything on garbage
            LOGGER.warning("Can not read counters from '%s' (%s), resetting counters", source, ex)
            self.data = self.default.copy()
            self.save()
            return

        if source == self.legacy_filename:
            LOGGER.info("Counters migrated from '%s' to '%s'", self.legacy_filename, self.filename)
            self.save()

    def _read_json(self):
        with open(self.filename, 'r', encoding='utf-8') as fp:
            return self._check_dict(json.load(fp))

    def _read_pickle(self):
        with open(self.legacy_filename, 'rb') as fp:
            return self._check_dict(pickle.load(fp))

    @staticmethod
    def _check_dict(data):
        if not isinstance(data, dict):
            raise ValueError("expected a dict, got {}".format(type(data).__name__))
        return data

    def reset(self):
        """Reset all counters.
        """
        self.data = self.default.copy()
        self.save()

    def save(self):
        """Save the current counters in the JSON file. The file is replaced
        atomically so that a power cut can not leave it truncated.
        """
        tmp_filename = self.filename + '.tmp'
        try:
            with open(tmp_filename, 'w', encoding='utf-8') as fp:
                json.dump(self.data, fp, indent=2)
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(tmp_filename, self.filename)
        except OSError as ex:
            LOGGER.error("Failed to save counters in '%s': %s", self.filename, ex)
            if osp.isfile(tmp_filename):
                os.remove(tmp_filename)
