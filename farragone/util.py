"""Farragone general utilities.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import sys
from time import time

from . import coreconf as conf

# displayed category names for warnings
WARNING_CAT = {
    'fields': _('fields'),
    'regex': _('invalid regular expression'),
    'component index': _('path component index must be an integer'),
    'template': _('invalid template'),

    # NOTE: 'source' as in source/destination
    'unresolved fields': _('fields are used but don\'t exist'),
    'source': _('invalid source file'),
    'dest': _('destination path is invalid'),
    'dest exists': _('destination file already exists'),
    'cross device': _(
        'source and destination on different disks (renaming will be slow)'
    ),
}


def warn (*args):
    """Print a general warning log."""
    # NOTE: log line
    print(_('warning: {}').format(' '.join(map(str, args))), file=sys.stderr)


def logger (name):
    """Create a logging function with the given name.

name: corresponds to `conf.LOG` keys

"""
    enabled = conf.LOG.get(name, False)
    prefix = '[{}]'.format(name)

    def log (*args):
        if enabled:
            print(prefix, *args, file=sys.stderr)

    return log


def rate_limit (min_interval, f):
    """Rate-limit calls to a function.

min_interval: minimum allowed time between any two calls, in seconds
f: function to call

Returns rate-limited function; all arguments are passed through to `f`.

"""
    last = 0

    def rate_limited (*args, **kwargs):
        nonlocal last
        if time() - last >= min_interval:
            f(*args, **kwargs)
            last = time()

    return rate_limited


def exc_str (e):
    """Get the error message for an exception as a string."""
    return ' '.join(map(str, e.args))


class Warn:
    def __init__ (self, category, detail):
        self.category = category
        self.detail = detail

    @property
    def category_name (self):
        return WARNING_CAT[self.category]

    @staticmethod
    def from_exc (category, exception):
        return Warn(category, exc_str(exception))
