"""Farragone input definitions.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import abc
import re
import os
from glob import iglob

glob_chars = re.compile('([*?[])')


# no glob.escape until 3.4
def escape_glob (path):
    """Escape a string glob pattern."""
    drive, path = os.path.splitdrive(path)
    return drive + glob_chars.sub(r'[\1]', path)


class Input (metaclass=abc.ABCMeta):
    """Defines a method for retrieving input paths."""

    @abc.abstractmethod
    def __iter__ (self):
        """Iterate over the instance to get the paths."""
        pass


class StaticInput (Input):
    """Use specific paths.

paths: paths to yield

Attributes:

paths: as passed to the constructor

"""

    def __init__ (self, *paths):
        self.paths = paths

    def __iter__ (self):
        return iter(self.paths)


class GlobInput (Input):
    """Use paths matching a glob-style pattern.

pattern: glob pattern
cwd: path that `pattern` is relative to, if not absolute (default: the process
     working directory)

Attributes:

pattern: as passed to the constructor

"""

    def __init__ (self, pattern, cwd=None):
        if cwd is None:
            cwd = os.getcwd()
        self.pattern = os.path.join(escape_glob(cwd),
                                    os.path.expanduser(pattern))

    def __iter__ (self):
        return iglob(self.pattern)


class RecursiveFilesInput (Input):
    """Recursively search a directory for files.

path: directory to search
cwd: path that `path` is relative to, if not absolute (default: the process
     working directory)

Attributes:

path: as passed to the constructor

"""

    def __init__ (self, path, cwd=None):
        self.path = os.path.join(cwd, os.path.expanduser(path))

    def __iter__ (self):
        # doesn't throw
        join = os.path.join
        for d, dirs, files in os.walk(self.path):
            for f in files:
                yield join(d, f)
