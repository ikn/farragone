"""Farragone UI utilities.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import sys

from . import conf


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
