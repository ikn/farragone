"""Farragone UI utilities.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import sys
from time import time

from .. import ui


def warn (*args):
    """Print a general warning log."""
    print('warning:', *args, file=sys.stderr)


def logger (name):
    """Create a logging function with the given name.

name: corresponds to `conf.LOG` keys

"""
    enabled = ui.conf.LOG.get(name, False)
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
