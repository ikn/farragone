"""Farragone configuration.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import os
import json

from . import util
from .coreconf import *

APPLICATION = _('Farragone')

for d in (PATH_CONF_WRITE,):
    try:
        os.makedirs(d, exist_ok = True)
    except OSError as e:
        util.warn(_('failed creating directory: {}:').format(repr(d)), e)


class _JSONEncoder (json.JSONEncoder):
    """Extended json.JSONEncoder with support for any iterable."""

    def default (self, o):
        if hasattr(o, '__iter__'):
            return list(o)
        else:
            return json.JSONEncoder.default(self, o)


class Settings (dict):
    """`dict`-like settings storage with JSON file backend.

load_fns: filenames to load from
save_fn: filename to save to
defn: `dict` with keys being available setting names and values being `dict`s
      with keys:
    default: the default value
    validate: a function taking a new value for the setting and returning a
              boolean indicating whether it's valid
    cast: a function taking a new value for the setting and returning the value
          to actually use (optional) (called after `validate`)

Use the `dict` interface to set and retrieve values; delete to reset to the
default value.  These operations raise `KeyError` for settings not in `defn`.

"""

    def __init__ (self, load_fns, save_fn, defn):
        self._log = util.logger('conf.settings')
        self.filename = save_fn
        self.definition = defn

        for key, item_defn in defn.items():
            self[key] = item_defn['default']
        for fn in load_fns:
            overrides = self._load(fn)
            for key, value in overrides.items():
                self[key] = value

    def _load (self, fn):
        # load settings from disk
        try:
            with open(fn) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise TypeError(data)
        except FileNotFoundError:
            return {}
        except (IOError, TypeError, ValueError) as e:
            # NOTE: placeholders are filename and system error message
            util.warn(_('loading settings from {0} failed: {1}')
                      .format(repr(fn), str(e)))
            return {}
        else:
            return data

    def _save (self):
        # save settings to disk
        fn = self.filename
        tmp_fn = fn + '.tmp'
        os.makedirs(os.path.dirname(fn), exist_ok=True)
        with open(tmp_fn, 'w') as f:
            json.dump(self, f, cls=_JSONEncoder)
        # can't rename if destination exists in Windows
        try:
            os.remove(fn)
        except FileNotFoundError:
            pass
        os.rename(tmp_fn, fn)

    def __setitem__ (self, key, value):
        self._log('set', key, value)
        if key in self.definition:
            if not self.definition[key]['validate'](value):
                raise TypeError(value)
            value = self.definition[key].get('cast', lambda x: x)(value)

            dict.__setitem__(self, key, value)
            try:
                self._save()
            except (IOError, OSError, TypeError) as e:
                # NOTE: placeholder is system error message
                util.warn(_('saving settings failed: {}').format(str(e)))
        else:
            raise KeyError(key)

    def __delitem__ (self, key):
        # raises KeyError
        self[key] = self.definition[key]['default']


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


settings = Settings(
    [join_path(path, CONF_FILENAME) for path in PATHS_CONF_READ],
    join_path(PATH_CONF_WRITE, CONF_FILENAME),
    {
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
        },
        'disabled_warnings': {
            'default': set(),
            'validate': lambda x: hasattr(x, '__iter__'),
            'cast': lambda x: set(x)
        }
    }
)
