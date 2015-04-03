"""Farragone temporary database for processed renames.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from os.path import join as join_path
import glob
import sqlite3

from . import rename

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
    'create': ('''
CREATE TABLE {tbl} (`frm` TEXT, `to` TEXT, `cmp_frm` TEXT, `cmp_to` TEXT);
CREATE INDEX `cmp_frm` ON {tbl} (`cmp_frm`);
CREATE INDEX `cmp_to` ON {tbl} (`cmp_to`);
    ''').format(tbl=_tbl),

    'drop': 'DROP TABLE {}'.format(_tbl),
    'add': 'INSERT INTO {} VALUES (:frm, :to, :cmp_frm, :cmp_to)'.format(_tbl),

    'find frm': _mk_select('`cmp_frm` = ?'),
    'find to': _mk_select('`cmp_to` = ?'),
    # collation defaults to BINARY, so these comparisons are case-insensitive
    'find frm parent': _mk_select('`cmp_frm` IN ({parents})'),
    'find frm child': _mk_select('? < `cmp_frm` AND `cmp_frm` < ?')
}


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


def _setup (con):
    """Initialise the database tables.

con: database connection.

"""
    con.executescript(_QUERIES['create'])


def create ():
    """Create and initialise a temporary renames database.

Returns a database connection.

"""
    # stored in memory or temp file, depending on available memory
    # https://www.sqlite.org/inmemorydb.html
    con = sqlite3.connect('')
    _setup(con)
    return con


def clear (con):
    """Remove all data from an existing database.

con: database connection

"""
    _exec(con, 'drop')
    _setup(con)


def add (con, frm, to, cmp_frm, cmp_to):
    """Add a rename to the database.

con: database connection
frm: source path
to: destination path
cmp_frm: comparable version of `frm`
cmp_to: comparable version of `to`

"""
    _exec(con, 'add', {
        'frm': frm, 'to': to, 'cmp_frm': cmp_frm, 'cmp_to': cmp_to
    })


def _get_one (con, qry_id, params=()):
    """Run a query performing a `select` and return the first record, if any.

con, qry_id, params: as taken by `_exec`

Returns a database record or `None`.

"""
    return next(_exec(con, qry_id, params), None)


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
    parents = tuple(rename.parents(cmp_child))
    qry = _QUERIES['find frm parent'].format(
        parents=', '.join('?' * len(parents)))
    cursor = con.cursor()
    cursor.execute(qry, parents)
    return next(cursor, None)


def find_frm_child (con, cmp_parent):
    """Find a rename in the database whose source path is a child of the given
path.

con: database connection
cmp_parent: comparable source path to search for children of

Returns `(frm, to)` or `None`.

"""

    child_lb = join_path(cmp_parent, '')
    child_ub = child_lb[:-1] + chr(ord(child_lb[-1]) + 1)
    return _get_one(con, 'find frm child', (child_lb, child_ub))
