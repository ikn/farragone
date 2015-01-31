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


def _ensure_dir_exists (path):
    """Create a directory and all missing intermediate directories.

Returns a sequence of the paths that were created, deepest first.

"""
    create = []
    while True:
        try:
            os.mkdir(path)
        except FileExistsError:
            # no need to create
            break
        except OSError as e:
            if e.errno == 2:
                # 'no such file or directory': need to create parent first
                create.append(path)
                path = os_path.dirname(path)
            else:
                raise
        else:
            # succeeded, so there's no need to look at parents
            # create children we failed to create before
            for child in reversed(create):
                os.mkdir(child)
            create.append(path)
            break
    return create


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


def _rename (frm, to):
    """Actually rename a file."""
    try:
        os.rename(frm, to)
    except OSError as e:
        if e.errno == 18:
            # 'invalid cross-device link': copy then delete
            _rename_cross_device(frm, to)
        else:
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

    if frm == to:
        pass
    elif os_path.exists(to):
        raise DestinationExistsError(to)
    else:
        created = _ensure_dir_exists(os_path.dirname(to))
        try:
            _rename(frm, to)
        except OSError:
            # remove created directories
            try:
                for path in created:
                    os.rmdir(path)
            except OSError:
                pass
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
