"""Farragone UI configuration.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import sys
from platform import system
import os
from os.path import join as join_path
import json

from . import util

IDENTIFIER = 'farragone'
APPLICATION = 'Farragone'
VERSION = '0.1.1-next'

LOG = {
    'qt.widgets.natural_widget_order': False,
    'qt.output:preview': False
}

if system() == 'Windows':
    HOME = os.environ['USERPROFILE']
    SHARE = join_path(os.environ['APPDATA'], IDENTIFIER)
    PATH_CONF = SHARE
else:
    HOME = os.path.expanduser('~')
    SHARE = join_path(HOME, '.local', 'share', IDENTIFIER)
    PATH_CONF = join_path(HOME, '.config', IDENTIFIER)
CONF_FILE = join_path(PATH_CONF, 'settings')

for d in set((PATH_CONF,)):
    try:
        os.makedirs(d, exist_ok = True)
    except OSError as e:
        util.warn('failed creating directory: {}:'.format(repr(d)), e)

# minumum interval between Qt signals for potentially rapid emitters
MIN_SIGNAL_INTERVAL = 0.2
# maximum number of renames shown in the preview
MAX_PREVIEW_LENGTH = 500
# used to find an icon theme
FALLBACK_DESKTOP = 'GNOME'


class Settings (dict):
    """`dict`-like settings storage with JSON file backend.

fn: filename to load from and save to
defn: `dict` with keys being available setting names and values being `dict`s:
      { 'default': default, 'validate': validate }.  `default` is the default
      value and `validate` is a function taking a new value for the setting and
      returning a boolean indicating whether it's valid.

Use the `dict` interface to set and retrieve values; delete to reset to the
default value.  These operations raise `KeyError` for settings not in `defn`.

"""

    def __init__ (self, fn, defn):
        self.filename = fn
        self.definition = defn

        overrides = {}
        try:
            overrides = self._load()
            if not isinstance(overrides, dict):
                raise TypeError(overrides)
        except FileNotFoundError:
            pass
        except (IOError, TypeError, ValueError) as e:
            util.warn('loading settings failed:', e)

        for key, item_defn in defn.items():
            self[key] = overrides.get(key, item_defn['default'])

    def _load (self):
        # load settings from disk
        with open(self.filename) as f:
            data = json.load(f)
        return data

    def _save (self):
        # save settings to disk
        fn = self.filename
        tmp_fn = fn + '.tmp'
        os.makedirs(os.path.dirname(fn), exist_ok=True)
        with open(tmp_fn, 'w') as f:
            json.dump(self, f)
        os.rename(tmp_fn, fn)

    def __setitem__ (self, key, value):
        if key in self.definition:
            if not self.definition[key]['validate'](value):
                raise TypeError(value)

            dict.__setitem__(self, key, value)
            try:
                self._save()
            except (IOError, OSError, TypeError) as e:
                util.warn('saving settings failed:', e)
        else:
            raise KeyError(key)

    def __delitem__ (self, key):
        # raises KeyError
        self[key] = self.definition[key]


def tuple_check (*types):
    """Check a tuple against a template.

types: sequence of types matching the expected tuple

Returns a function that takes an object and returns whether it is a lists or
tuple, has the correct length, and has items with the expected types.

"""
    def check (xs):
        return (isinstance(xs, (list, tuple)) and
                len(xs) == len(types) and
                all(isinstance(x, t) for x, t in zip(xs, types)))

    return check


settings = Settings(join_path(CONF_FILE), {
    # automatic
    'win_size_main': {
        'default': (600, 600),
        'validate': tuple_check(int, int)
    },
    'win_max_main': {
        'default': False,
        'validate': lambda x: isinstance(x, bool)
    },
    'splitter_ratio_main': {
        'default': .5,
        'validate': lambda x: isinstance(x, (int, float)) and 0 <= x <= 1
    }
})
