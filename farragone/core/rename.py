# coding=utf-8
"""Farragone renaming routines.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import itertools
import os
import shutil

from .. import conf, util


def fmt_path (path):
    return repr(path.replace(os.sep, '/') if conf.WINDOWS else path)


def preview_rename (frm, to):
    """Return a string displaying a rename operation."""
    # NOTE: rename preview: source -> destination
    return _('{0} → {1}').format(fmt_path(frm), fmt_path(to))


# given a file path, return one that can be safely compared to others
comparable_path = os.path.normcase


def _get_abs_path (path, cwd):
    """Make a path absolute.

path: relative or absolute path
cwd: directory that `path` is relative to; must be absolute

"""
    path = os.path.expanduser(path)
    return os.path.normpath(os.path.join(cwd, path))


def parents (path, include_full=False, allow_empty=True):
    """Get parents of a path.

path: path to get all parents of
include_full: whether to also get `path` itself
allow_empty: the returned iterator may be empty; if `False` and `path` is root,
             we yield `path`.

Returns an iterator over parent paths.  The order is children before parents.

"""
    found = False
    if include_full:
        yield path
        found = True

    while True:
        new_path = os.path.dirname(path)
        if new_path == path:
            if not found and not allow_empty:
                yield path
            break
        else:
            yield new_path
            found = True
            path = new_path


class DestinationExistsError (OSError):
    """Failed to rename a file because the destination path already exists."""
    def __init__ (self, dest):
        # NOTE: trying to rename to a file that already exists
        OSError.__init__(
            self, _('destination exists: {}').format(fmt_path(dest)))


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
                path = os.path.dirname(path)
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
    is_dir = os.path.isdir(frm) and not os.path.islink(frm)
    try:
        if is_dir:
            shutil.copytree(frm, to, symlinks=True)
            shutil.rmtree(frm)
        else:
            shutil.copy2(frm, to, follow_symlinks=False)
            os.remove(frm)
    except OSError:
        # try to clean up
        try:
            if is_dir:
                shutil.rmtree(to)
            else:
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

`frm` and `to` must be absolute, normalised paths.

Raises OSError.

"""
    if (os.path.normcase(frm) == os.path.normcase(to)):
        pass
    elif os.path.exists(to):
        raise DestinationExistsError(to)
    else:
        created = _ensure_dir_exists(os.path.dirname(to))
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


def _get_renames (with_warnings, inps, fields, template, cwd=None):
    """Like `get_renames`, but possibly including warnings.

with_warnings: whether to compute warnings that can only be determined while
               determining the source and destination paths.

Returns `(renames, done)` like `get_renames`; `renames` yields
`(input_path, output_path, warnings)`, where warnings is a sequence of util.Warn
instances (empty if `with_warnings` is False).

"""
    if cwd is None:
        cwd = os.getcwd()
    cwd = os.path.abspath(cwd)

    paths = itertools.chain.from_iterable(inps)
    abs_paths = map(lambda path: _get_abs_path(path, cwd), paths)
    result, state = fields.evaluate(abs_paths)

    def get ():
        for path, field_vals in result:
            warnings = []
            dest_path = None

            if with_warnings:
                try:
                    dest_path = template.substitute(field_vals)
                except ValueError:
                    pass
                except KeyError as e:
                    # NOTE: warning detail for unknown fields; placeholders are
                    # the source filename and the field names
                    detail = _('{0}: fields: {1}').format(
                        fmt_path(path), ', '.join(map(repr, e.args)))
                    warnings.append(util.Warn('unresolved fields', detail))

            if dest_path is None:
                dest_path = template.safe_substitute(field_vals)
            yield (path, _get_abs_path(dest_path, cwd), warnings)

    return (get(), lambda: fields.cleanup(state))


def get_renames (*args, **kwargs):
    """Get files to rename and destination paths.

inps: sequence of `inputs.Input` to retrieve paths from
fields: `field.Fields` instance defining fields to retrieve from input paths
template: `string.Template` instance to generate output paths using retrieved
          fields
cwd: directory that relative paths are relative to (default: the working
     directory of this process)

Returns `(get, done)`, where:

renames: an iterator yielding `(input_path, output_path)` tuples, where both
         paths are absolute
done: function to call with no arguments to clean up some internal state when
      finished

"""
    renames, done = _get_renames(False, *args, **kwargs)

    def get ():
        for frm, to, warnings in renames:
            yield (frm, to)

    return (get(), done)
