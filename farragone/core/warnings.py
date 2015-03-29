"""Farragone problem checking and warning generation.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import itertools
from functools import partial
import os

from .. import util, conf
from . import rename, renamesdb


def path_invalid (path):
    """Determine if a path is invalid.

Detects problems which will not cause an error to be raised when using the path.

Returns a string with the reason for the path being invalid, or None.

"""
    if conf.WINDOWS:
        if path.endswith('.') or path.endswith(' '):
            return _(
                'trailing spaces and dots will be removed from the filename'
            )


def path_device (path):
    """Determine the device containing the given path."""
    dev = None
    while True:
        try:
            dev = os.stat(path, follow_symlinks=False).st_dev
        except FileNotFoundError:
            new_path = os.path.dirname(path)
            if new_path == path:
                dev = None
                break
            else:
                path = new_path
        except OSError:
            break
        else:
            break
    return dev


def _check_same_warning (cat, existing_rename, new_rename):
    """Yield warnings for duplicate source/destination paths.

cat: warning category to use
existing_rename: `(frm, to)` or `None` for the matching rename
new_rename: `(frm, to)` for rename being checked

"""
    if existing_rename is not None:
        detail = '{}, {}'.format(
            rename.preview_rename(*existing_rename),
            rename.preview_rename(*new_rename)
        )
        yield util.Warn(cat, detail)


def _check_frm_parent_warning (existing_rename, new_frm):
    """Yield warnings for clashing source paths (one is a parent of another).

existing_rename: `(frm, to)` or `None` for the clashing rename
new_frm: source path for rename being checked

"""
    if existing_rename is not None:
        detail = '{}, {}'.format(repr(existing_rename[0]), repr(new_frm))
        yield util.Warn('source parent', detail)


def _get_dependent_warnings (con, new_frm, new_to):
    """Get warnings for a new rename that depend on previous renames.

con: database connection
new_frm: source path for new rename
new_to: destination path for new rename

Returns sequence of util.Warn instances.

Should only be called once for each rename.

"""
    cmp_new_frm = rename.comparable_path(new_frm)
    cmp_new_to = rename.comparable_path(new_to)
    warnings = []

    try:
        rename_same_frm = renamesdb.find_frm(con, cmp_new_frm)
        rename_same_to = renamesdb.find_to(con, cmp_new_to)
        rename_frm_parent = renamesdb.find_frm_parent(con, cmp_new_frm)
        rename_frm_child = renamesdb.find_frm_child(con, cmp_new_frm)
    except renamesdb.Error as e:
        warnings.append(util.Warn.from_exc('unknown', e))
    else:
        warnings.extend(itertools.chain(
            _check_same_warning('dup source', rename_same_frm,
                                (new_frm, new_to)),
            _check_same_warning('dup dest', rename_same_to, (new_frm, new_to)),
            _check_frm_parent_warning(rename_frm_parent, new_frm),
            _check_frm_parent_warning(rename_frm_child, new_frm)
        ))

    renamesdb.add(con, new_frm, new_to, cmp_new_frm, cmp_new_to)
    return warnings


def _get_renames_with_warnings (con, warnings, *args, **kwargs):
    """Like `get` returned by `get_renames_with_warnings`.

con: database connection (possibly `None`)
warnings: sequence of initial warnings (only yielded once)

Other arguments are as taken by `get`.

"""
    warnings = list(warnings)

    for frm, to, new_warnings in rename._get_renames(True, *args, **kwargs):
        warnings.extend(new_warnings)

        if not os.path.exists(frm):
            warnings.append(util.Warn('source', repr(frm)))

        detail = path_invalid(to)
        if detail is not None:
            warnings.append(
                # NOTE: warning detail for an invalid destination path;
                # placeholders are the path and the problem with it
                util.Warn('dest', '{0}: {1}'.format(repr(to), detail)))

        if os.path.exists(to):
            warnings.append(
                util.Warn('dest exists', rename.preview_rename(frm, to)))

        if path_device(frm) != path_device(to):
            warnings.append(
                util.Warn('cross device', rename.preview_rename(frm, to)))

        if con is not None:
            warnings.extend(_get_dependent_warnings(con, frm, to))

        yield ((frm, to), warnings)
        warnings = []


def get_renames_with_warnings ():
    """Get files to rename and destination paths, with associated warnings.

Returns `(get, done)`, where:

get: function to call to get renames.  Arguments are as taken by `get_renames`.
     Returns an iterator yielding `(rename, warnings)`, where `rename` is as
     yielded by `get_renames` and `warnings` is a sequence of
     util.Warn instances.
done: function to call with no arguments to clean up some internal state when
      finished

"""
    con = None
    con_err = None
    try:
        con = renamesdb.create()
    except renamesdb.Error as e:
        con_err = e

    def quit ():
        nonlocal con
        if con is not None:
            con.close()
            con = None

    return (partial(
        _get_renames_with_warnings, con,
        [] if con_err is None else [util.Warn.from_exc('unknown', con_err)]
    ), quit)
