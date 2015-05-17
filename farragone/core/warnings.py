"""Farragone problem checking and warning generation.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import itertools
import os

from .. import util, conf
from . import rename, db


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


def _find_check (query, mk_warning):
    """Run a `db` query to get a warning as a single rename.

query: function to call which returns a `(frm, to)` rename to use in creating a
       warning
mk_warning: function to call with the rename from `query` if not None; should
            return a `util.Warn` instance

Returns an iterator of `util.Warn` instances from `mk_warning`

"""
    rename = query()
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


def _get_dependent_warnings (wdb, frm, to):
    """Get warnings for a new rename that depend on previous renames.

wdb: `RenamesDBWithWarnings`
frm: source path for new rename
to: destination path for new rename

Returns sequence of util.Warn instances.

Should only be called once for each rename.

"""
    cmp_frm = rename.comparable_path(frm)
    cmp_to = rename.comparable_path(to)
    warnings = []

    # check for duplicates
    same_frm_warnings = tuple(_find_check(
        lambda: wdb.find_frm(cmp_frm),
        lambda rename: _same_warning('dup source', rename, (frm, to))
    ))
    warnings.extend(same_frm_warnings)
    warnings.extend(_find_check(
        lambda: wdb.find_to(cmp_to),
        lambda rename: _same_warning('dup dest', rename, (frm, to))
    ))

    # if not a duplicate, check for children
    if not same_frm_warnings:
        frm_child_warnings = tuple(_find_check(
            lambda: wdb.find_frm_child(cmp_frm),
            lambda rename: _frm_parent_warning(rename, frm)
        ))
        warnings.extend(frm_child_warnings)

        # if not a parent, check for parents
        if not frm_child_warnings:
            warnings.extend(_find_check(
                lambda: wdb.find_frm_parent(cmp_frm),
                lambda rename: _frm_parent_warning(rename, frm)
            ))

    wdb.add(frm, to)
    return warnings


def _get_renames_with_warnings (wdb, inps, fields, template,
                                *args, **kwargs):
    """Like `get_renames_with_warnings`.

wdb: `RenamesDBWithWarnings`

Other arguments are as taken by `get_renames_with_warnings`.

"""
    renames, done = rename._get_renames(
        True, inps, fields, template, *args, **kwargs)

    def get ():
        warnings = []

        try:
            template.substitute()
        except ValueError as e:
            warnings.append(util.Warn('template', util.exc_str(e)))
        except KeyError:
            pass

        for frm, to, new_warnings in renames:
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

            warnings.extend(_get_dependent_warnings(wdb, frm, to))

            yield ((frm, to), warnings)
            warnings = []

    return (get(), done)


def get_renames_with_warnings (*args, **kwargs):
    """Get files to rename and destination paths, with associated warnings.

Arguments are as taken by `get_renames`.

Returns `(renames, done)`, like `get_renames`; `renames` yields
`((input_path, output_path), warnings)`, where `warnings` is a sequence of
util.Warn instances.

"""
    wdb = db.RenamesDBWithWarnings()
    renames, done_core = _get_renames_with_warnings(wdb, *args, **kwargs)

    def done ():
        done_core()
        wdb.close()

    return (renames, done)
