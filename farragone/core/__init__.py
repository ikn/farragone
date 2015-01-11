"""Farragone core functionality.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import itertools
import os
from os import path as os_path
import shutil

from . import inputs, field



def _get_abs_path (path, cwd=None):
    """Make a path absolute.

path: relative or absolute path
cwd: directory that `path` is relative to (default: Python process's current
     working directory)

"""
    abs_path = os_path.abspath(path)
    return (
        os_path.normpath(os_path.join(cwd, path))
        if cwd is not None and abs_path != path
        else abs_path
    )


class DestinationExistsError (OSError):
    """Failed to rename a file because the destination path already exists."""
    def __init__ (self, dest):
        OSError.__init__(self, 'destination exists: {}'.format(repr(dest)))


def _rename_cross_device (frm, to):
    """Rename a file across mount points."""
    try:
        shutil.copy2(frm, to)
        os.remove(frm)
    except OSError:
        # try to clean up
        try:
            os.remove(to)
        except OSError:
            pass
        raise


def rename (frm, to):
    """Rename a file.

frm: current path
to: destination path

`frm` and `to` must be absolute paths.

Raises OSError.

"""
    frm = os_path.realpath(os_path.normcase(frm))
    to = os_path.realpath(os_path.normcase(to))

    if os_path.exists(to):
        raise DestinationExistsError(to)
    else:
        try:
            os.makedirs(os_path.dirname(to), exist_ok=True)
            os.rename(frm, to)
        except OSError as e:
            if e.errno == 18:
                # 'invalid cross-device link': copy then delete
                _rename_cross_device(frm, to)
            else:
                raise


def get_renames (inps, fields, template, fields_transform=lambda f: f,
                 cwd=None):
    """Get files to rename and destination paths.

inps: sequence of `inputs.Input` to retrieve paths from
fields: `field.Fields` instance defining fields to retrieve from input paths
template: `string.Template` instance to generate output paths using retrieved
          fields
fields_transform: function taking a fields `dict` and producing another
cwd: directory that relative paths are relative to (default: the working
     directory of this process)

Returns an iterator yielding `(input_path, output_path)` pairs, where both
paths are absolute.

"""
    if cwd is not None:
        cwd = os_path.abspath(cwd)

    paths = itertools.chain.from_iterable(inps)
    abs_paths = map(lambda path: _get_abs_path(path, cwd), paths)
    paths1, paths2 = itertools.tee(abs_paths, 2)

    for path, field_vals in zip(
        paths2, map(fields_transform, fields.evaluate(paths1))
    ):
        yield (path, _get_abs_path(template.safe_substitute(field_vals), cwd))
