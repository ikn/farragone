"""Farragone temporary database for processed renames.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import abc
from os.path import join as join_path
import sqlite3

from . import rename

# escaped table name
_tbl = '`temp`'


def key_to_sqlite_cmp (key):
    """Turn a sorting 'key' function into a sqlite3 collation function."""

    def cmp_fn (a, b):
        # Python documentation says these arguments should be `bytes`, but
        # they're actually `str`
        a_cmp = key(a)
        b_cmp = key(b)
        return -1 if a_cmp < b_cmp else (0 if a_cmp == b_cmp else 1)

    return cmp_fn


def _mk_select (where):
    """Return a `select` SQL query.

where: SQL `where` clause body

The query selects the `frm` and `to` columns for at most one record.

"""
    return 'SELECT `frm`, `to` FROM {tbl} WHERE ' + where + ' LIMIT 1'


class DB (metaclass=abc.ABCMeta):
    """

tbls: sequence of table names (SQL-escaped) - used by `clear` to drop them
init: initialisation function run after opening the connection and before
      creating tables

"""

    # query string used to initialise the database (multiple queries allowed)
    _CREATE_QUERY = None
    # queries by identifier
    _QUERIES = {
        'drop': 'DROP TABLE {tbl}'
    }

    def __init__ (self, tbls=(_tbl,), init=None):
        self._tbls = tbls
        # stored in memory or temp file, depending on available memory
        # creates a different database for each connection
        # https://www.sqlite.org/inmemorydb.html
        self.con = sqlite3.connect('')
        if init:
            init()
        self._setup()

    def close (self):
        # close the connection
        if self.con is not None:
            self.con.close()
            self.con = None

    def _exec (self, qry_id, params=(), options={}):
        """Execute an SQL query.

qry_id: key in `self._QUERIES`
params: sequence or dict of parameters to substitute into the query
options: passed to `str.format` on the query string

Returns the cursor used to execute the query.

"""
        cursor = self.con.cursor()
        cursor.execute(self._QUERIES[qry_id].format(**options), params)
        return cursor

    def _setup (self):
        """Initialise the database tables."""
        self.con.executescript(self._CREATE_QUERY)

    def clear (self):
        """Remove all data."""
        for tbl in self._tbls:
            self._exec('drop', options={'tbl': tbl})
        self._setup()


class RenamesDBWithWarnings (DB):
    _tbl = _tbl
    _CREATE_QUERY = '''
CREATE TABLE {tbl} (`frm` TEXT, `to` TEXT, `cmp_frm` TEXT, `cmp_to` TEXT);
CREATE INDEX `cmp_frm` ON {tbl} (`cmp_frm`);
CREATE INDEX `cmp_to` ON {tbl} (`cmp_to`);
    '''.format(tbl=_tbl)

    _QUERIES = {}
    _QUERIES.update(DB._QUERIES)
    _QUERIES.update({
        'add': 'INSERT INTO {tbl} VALUES (:frm, :to, :cmp_frm, :cmp_to)',
        'find frm': _mk_select('`cmp_frm` = ?'),
        'find to': _mk_select('`cmp_to` = ?'),
        # collation defaults to BINARY, so these comparisons are
        # case-insensitive
        'find frm parent': _mk_select('`cmp_frm` IN ({parents})'),
        'find frm child': _mk_select('? < `cmp_frm` AND `cmp_frm` < ?')
    })

    def __init__ (self):
        DB.__init__(self)


    def add (self, frm, to):
        """Add a rename to the database.

frm: source path
to: destination path

"""
        self._exec('add', {
            'frm': frm, 'to': to,
            'cmp_frm': rename.comparable_path(frm),
            'cmp_to': rename.comparable_path(to)
        }, {'tbl': self._tbl})


    def _get_one (self, qry_id, params=(), options={}):
        """Run a query performing a `select` and return the first record, if
any.

Arguments are as taken by `DB._exec`.

Returns a database record or `None`.

"""
        options = options.copy()
        options.setdefault('tbl', self._tbl)
        return next(self._exec(qry_id, params, options), None)


    def find_frm (self, cmp_frm):
        """Find a rename in the database with the given source path.

cmp_frm: comparable source path to search for

Returns `(frm, to)` or `None`.

"""
        return self._get_one('find frm', (cmp_frm,))


    def find_to (self, cmp_to):
        """Find a rename in the database with the given destination path.

cmp_to: comparable destination path to search for

Returns `(frm, to)` or `None`.

"""
        return self._get_one('find to', (cmp_to,))


    def find_frm_parent (self, cmp_child):
        """Find a rename in the database whose source path is a parent of the
given path.

cmp_child: comparable source path to search for parents of

Returns `(frm, to)` or `None`.

"""
        parents = tuple(rename.parents(cmp_child))
        return self._get_one('find frm parent', parents, {
            'parents': ', '.join('?' * len(parents))
        })


    def find_frm_child (self, cmp_parent):
        """Find a rename in the database whose source path is a child of the
given path.

cmp_parent: comparable source path to search for children of

Returns `(frm, to)` or `None`.

"""
        child_lb = join_path(cmp_parent, '')
        child_ub = child_lb[:-1] + chr(ord(child_lb[-1]) + 1)
        return self._get_one('find frm child', (child_lb, child_ub))


class OrderingDB (DB):
    # we read into one table, then copy into another with the desired order,
    # then read from that sorted by original order
    _tbl_opts = {'tbl1': '`temp1`', 'tbl2': '`temp2`'}
    _collation = 'custom_collation'

    _CREATE_QUERY = '''
CREATE TABLE {tbl1} (`path` TEXT COLLATE {collation}, `full_path` TEXT);
CREATE INDEX `path` ON {tbl1} (`path`);
CREATE TABLE {tbl2} (`order` INTEGER, `full_path` TEXT);
CREATE INDEX `order` ON {tbl2} (`order`);
'''.format(collation=_collation, **_tbl_opts)

    _QUERIES = {}
    _QUERIES.update(DB._QUERIES)
    _QUERIES.update({
        'add': 'INSERT INTO {tbl1} VALUES (:path, :full_path)',
        'sort': '''
    INSERT INTO {tbl2} SELECT ROWID, `full_path` FROM {tbl1}
        ORDER BY `path` {order}
''',
        'get sorted': 'SELECT ROWID, `full_path` FROM {tbl2} ORDER BY `order`'
    })

    def __init__ (self, key, reverse):
        self.reverse = reverse
        DB.__init__(self, tuple(self._tbl_opts.values()),
                    lambda: self._init(key_to_sqlite_cmp(key)))

    def _init (self, cmp_fn):
        self.con.create_collation(self._collation, cmp_fn)

    def add (self, path, full_path):
        """Add a path to the store.

path: to use in sorting
full_path: original path, to yield in `get_sorted`

"""
        self._exec('add', {
            'path': path,
            'full_path': full_path
        }, options=self._tbl_opts)

    def sort (self):
        # sort stored paths internally
        order = 'DESC' if self.reverse else 'ASC'
        self._exec('sort', options=dict(self._tbl_opts, order=order))

    def get_sorted (self):
        """Retrieve sorted paths (`get_sorted` must have been called).

Returns an iterator of `(index, full_path)` tuples, with `index` starting at 1,
and `full_path` as passed to `add`, in the same order as calls to `add`.

"""
        return self._exec('get sorted', options=self._tbl_opts)
