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


def safe_stat (path):
    try:
        return os.stat(path, follow_symlinks=False)
    except NotImplementedError:
        return os.stat(path)


def safe_access (path, mode):
    try:
        return os.access(path, mode, follow_symlinks=False)
    except NotImplementedError:
        return os.access(path, mode)


def path_device (path):
    """Determine the device containing the given path."""
    dev = None
    for parent in rename.parents(path, True):
        try:
            dev = safe_stat(parent).st_dev
        except (FileNotFoundError, NotADirectoryError):
            pass
        except OSError:
            break
        else:
            break
    return dev


def path_nearest_parent (path):
    """Get the nearest existing parent of the given path."""
    nearest_parent = None
    for parent in rename.parents(path, allow_empty=False):
        if os.path.exists(parent):
            nearest_parent = parent
            break
    # in case os.path.exists gives False for root for some reason, use the last
    # parent we found
    return parent if nearest_parent is None else nearest_parent


def _try_find_check (query, mk_warning):
    """Run a `renamesdb` query to get a warning as a single rename.

query: function to call which may throw `renamesdb.Error`, and returns a
       `(frm, to)` rename to use in creating a warning
mk_warning: function to call with the rename from `query` if not None; should
            return a `util.Warn` instance

Returns an iterator of `util.Warn` instances (from `mk_warning`, or if `query`
threw).

"""
    try:
        rename = query()
    except renamesdb.Error as e:
        yield util.Warn.from_exc('unknown', e)
    else:
        if rename is not None:
            yield mk_warning(rename)


def _same_warning (cat, existing_rename, new_rename):
    """Return warning for duplicate source/destination paths.

cat: warning category to use
existing_rename: `(frm, to)` for the matching rename
new_rename: `(frm, to)` for rename being checked

"""
    detail = '{}, {}'.format(
        rename.preview_rename(*existing_rename),
        rename.preview_rename(*new_rename)
    )
    return util.Warn(cat, detail)


def _frm_parent_warning (existing_rename, new_frm):
    """Return warning for clashing source paths (one is a parent of another).

existing_rename: `(frm, to)` for the clashing rename
new_frm: source path for rename being checked

"""
    detail = '{}, {}'.format(rename.fmt_path(existing_rename[0]),
                             rename.fmt_path(new_frm))
    return util.Warn('source parent', detail)


def _get_dependent_warnings (con, frm, to):
    """Get warnings for a new rename that depend on previous renames.

con: database connection
frm: source path for new rename
to: destination path for new rename

Returns sequence of util.Warn instances.

Should only be called once for each rename.

"""
    cmp_frm = rename.comparable_path(frm)
    cmp_to = rename.comparable_path(to)
    warnings = []

    # check for duplicates
    same_frm_warnings = tuple(_try_find_check(
        lambda: renamesdb.find_frm(con, cmp_frm),
        lambda rename: _same_warning('dup source', rename, (frm, to))
    ))
    warnings.extend(same_frm_warnings)
    warnings.extend(_try_find_check(
        lambda: renamesdb.find_to(con, cmp_to),
        lambda rename: _same_warning('dup dest', rename, (frm, to))
    ))

    # if not a duplicate, check for children
    if not same_frm_warnings:
        frm_child_warnings = tuple(_try_find_check(
            lambda: renamesdb.find_frm_child(con, cmp_frm),
            lambda rename: _frm_parent_warning(rename, frm)
        ))
        warnings.extend(frm_child_warnings)

        # if not a parent, check for parents
        if not frm_child_warnings:
            warnings.extend(_try_find_check(
                lambda: renamesdb.find_frm_parent(con, cmp_frm),
                lambda rename: _frm_parent_warning(rename, frm)
            ))

    renamesdb.add(con, frm, to, cmp_frm, cmp_to)
    return warnings


def _get_renames_with_warnings (con, warnings, inps, fields, template, *args,
                                **kwargs):
    """Like `get` returned by `get_renames_with_warnings`.

con: database connection (possibly `None`)
warnings: sequence of initial warnings (only yielded once)

Other arguments are as taken by `get`.

"""
    warnings = list(warnings)

    try:
        template.substitute()
    except ValueError as e:
        warnings.append(util.Warn('template', util.exc_str(e)))
    except KeyError:
        pass

    for frm, to, new_warnings in rename._get_renames(
        True, inps, fields, template, *args, **kwargs
    ):
        warnings.extend(new_warnings)

        if not os.path.exists(frm):
            warnings.append(util.Warn('source', rename.fmt_path(frm)))
        elif not safe_access(frm, os.R_OK):
            warnings.append(util.Warn('source perm', rename.fmt_path(frm)))

        detail = path_invalid(to)
        if detail is not None:
            warnings.append(util.Warn(
                # NOTE: warning detail for an invalid destination path;
                # placeholders are the path and the problem with it
                'dest', '{0}: {1}'.format(rename.fmt_path(to), detail)))

        if os.path.exists(to):
            warnings.append(
                util.Warn('dest exists', rename.preview_rename(frm, to)))
        else:
            to_nearest_parent = path_nearest_parent(to)
            if (
                # can't write to subdirs of files
                not os.path.isdir(to_nearest_parent) or
                not safe_access(to_nearest_parent, os.W_OK)
            ):
                warnings.append(util.Warn('dest perm', rename.fmt_path(to)))

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
