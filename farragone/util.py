"""Farragone general utilities.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import sys
import itertools
from time import time
from html import escape

from . import coreconf as conf

# displayed category names for warnings
WARNING_CAT = {
    'unknown': _('computing warnings failed'),

    'fields': _('fields'),
    'regex': _('invalid regular expression'),
    'component index': _('path component index must be an integer'),
    'template': _('invalid template'),

    'unresolved fields': _('fields are used but don\'t exist'),
    # NOTE: 'source' as in source/destination
    'source': _('missing source file'),
    'source perm': _('cannot read from source file'),
    'dest': _('destination path is invalid'),
    'dest exists': _('destination file already exists'),
    'dest perm': _('cannot write to destination file'),
    'cross device': _(
        'source and destination on different disks (renaming will be slow)'
    ),

    # NOTE: 'source' as in source/destination
    'dup source': _('same source path specified twice'),
    'dup dest': _('same destination path specified twice'),
    # NOTE: 'source' as in source/destination
    'source parent': _('one source path is a parent of another')
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


def consume (i, interrupt=None):
    """Run through an iterator.

interrupt: abort when this function returns True

"""
    for x in i:
        if interrupt is not None and interrupt():
            break


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
    """A warning generated from the rename configuration.

category: string from `WARNING_CAT` keys
detail: string giving more information

"""

    def __init__ (self, category, detail):
        self.category = category
        self.detail = detail

    @staticmethod
    def from_exc (category, exception):
        """Create a `Warn` instance from an exception.

category: as taken by the constructor
exception: `Exception` instance

"""
        return Warn(category, exc_str(exception))


class Warnings (dict):
    """A collection of `Warn` instances.

max_per_category: maximum number of warnings to store per category

Indexing by category returns a sequence of `Warn` instances stored for that
category.

Truthy if it contains any warnings.

"""

    def __init__ (self, max_per_category=conf.MAX_WARNINGS_PER_CATEGORY):
        self.max_per_category = max_per_category
        self._warnings = {}

    def __bool__ (self):
        return bool(self._warnings)

    def __getitem__ (self, category):
        return self._warnings[category]['details']

    @property
    def categories (self):
        """Return an iterator over categories."""
        return self._warnings.keys()

    @property
    def warnings (self):
        """Return an iterator over all stored warnings."""
        return itertools.chain.from_iterable(self._warnings.values())

    def count (self, category):
        """Return the number of warnings added for the given category (not just
stored warnings."""
        warnings = self._warnings[category]
        return len(warnings['details']) + warnings['extra']

    @property
    def total (self):
        """Return the total number of warnings added (not just stored
warnings)."""
        return sum(map(self.count, self.categories))

    def add (self, warning):
        """Add a warning (`Warn` instance)."""
        existing = self._warnings.setdefault(
            warning.category, {'details': [], 'extra': 0})

        if (existing['extra'] or
            len(existing['details']) == conf.MAX_WARNINGS_PER_CATEGORY):
            existing['extra'] += 1
        else:
            existing['details'].append(warning.detail)

    def _render_html (self):
        """Render HTML output."""
        lines = []
        for category, warnings in self._warnings.items():
            lines.append('<b>{}</b>'.format(escape(WARNING_CAT[category])))
            for detail in warnings['details']:
                lines.append(escape(detail))

            extra = warnings['extra']
            if extra:
                # NOTE: for warnings display, where there are extra warnings in
                # a category not displayed; placeholder is how many of these
                # there are
                text = ngettext('(and {} more)', '(and {} more)', extra)
                lines.append('<i>{}</i>'.format(text.format(extra)))

            # gap between each category
            lines.append('')
        return '<br>'.join(lines)

    def render (self, fmt='html'):
        """Return a representation of the added warnings in a particular format.

fmt: format to use; allowed values are:
    'html': HTML (non-semantic)

"""
        render = {
            'html': self._render_html
        }.get(fmt)

        if render is None:
            raise ValueError('unknown render format', fmt)
        else:
            return render()
