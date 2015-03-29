"""Farragone temporary database for processed renames.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from os.path import join as join_path
import glob
import sqlite3

# thrown by all methods
Error = sqlite3.Error

# escaped table name
_tbl = '`renames`'


def _mk_select (where):
    """Return a `select` SQL query.

where: SQL `where` clause body

The query selects the `frm` and `to` columns for at most one record.

"""
    return 'SELECT `frm`, `to` FROM {} WHERE {} LIMIT 1'.format(_tbl, where)


# queries by identifier
_QUERIES = {
    'create': ('''CREATE TABLE {} (
        `frm` TEXT, `to` TEXT, `cmp_frm` TEXT, `cmp_to` TEXT,
        `frm_child_pattern` TEXT
    )''').format(_tbl),

    'drop': 'DROP TABLE {}'.format(_tbl),
    'add': '''INSERT INTO {} VALUES (
        :frm, :to, :cmp_frm, :cmp_to, :frm_child_pattern
    )'''.format(_tbl),

    'find frm': _mk_select('`cmp_frm` = ?'),
    'find to': _mk_select('`cmp_to` = ?'),
    'find frm parent': _mk_select('? GLOB `frm_child_pattern`'),
    'find frm child': _mk_select('`cmp_frm` GLOB ?')
}


def _child_pattern (cmp_parent):
    """Return a glob pattern that matches children of a path.

cmp_parent: comparable path to match children of

"""
    return glob.escape(join_path(cmp_parent, '')) + '?*'


def _exec (con, qry_id, params=()):
    """Execute an SQL query.

con: database connection
qry_id: key in `_QUERIES`
params: sequence or dict of parameters to substitute into the query

Returns the cursor used to execute the query.

"""
    cursor = con.cursor()
    cursor.execute(_QUERIES[qry_id], params)
    return cursor


def create ():
    """Create and initialise a temporary renames database.

Returns a database connection.

"""
    # stored in memory or temp file, depending on available memory
    # https://www.sqlite.org/inmemorydb.html
    con = sqlite3.connect('')
    _exec(con, 'create')
    return con


def clear (con):
    """Remove all data from an existing database.

con: database connection

"""
    _exec(con, 'drop')
    _exec(con, 'create')


def add (con, frm, to, cmp_frm, cmp_to):
    """Add a rename to the database.

con: database connection
frm: source path
to: destination path
cmp_frm: comparable version of `frm`
cmp_to: comparable version of `to`

"""
    _exec(con, 'add', {
        'frm': frm, 'to': to, 'cmp_frm': cmp_frm, 'cmp_to': cmp_to,
        'frm_child_pattern': _child_pattern(cmp_frm)
    })


def _get_one (con, qry_id, params=()):
    """Run a query performing a `select` and return the first record, if any.

con, qry_id, params: as taken by `_exec`

Returns a database record or `None`.

"""
    try:
        existing_rename = next(_exec(con, qry_id, params))
    except StopIteration:
        existing_rename = None
    return existing_rename


def find_frm (con, cmp_frm):
    """Find a rename in the database with the given source path.

con: database connection
cmp_frm: comparable source path to search for

Returns `(frm, to)` or `None`.

"""
    return _get_one(con, 'find frm', (cmp_frm,))


def find_to (con, cmp_to):
    """Find a rename in the database with the given destination path.

con: database connection
cmp_to: comparable destination path to search for

Returns `(frm, to)` or `None`.

"""
    return _get_one(con, 'find to', (cmp_to,))


def find_frm_parent (con, cmp_child):
    """Find a rename in the database whose source path is a parent of the given
path.

con: database connection
cmp_child: comparable source path to search for parents of

Returns `(frm, to)` or `None`.

"""
    return _get_one(con, 'find frm parent', (cmp_child,))


def find_frm_child (con, cmp_parent):
    """Find a rename in the database whose source path is a child of the given
path.

con: database connection
cmp_parent: comparable source path to search for children of

Returns `(frm, to)` or `None`.

"""
    return _get_one(con, 'find frm child', (_child_pattern(cmp_parent),))
