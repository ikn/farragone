"""Farragone input definitions.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import abc
import os
from glob import iglob


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

Attributes:

pattern: as passed to the constructor

"""

    def __init__ (self, pattern):
        self.pattern = os.path.expanduser(pattern)

    def __iter__ (self):
        return iglob(self.pattern)


class RecursiveFilesInput (Input):
    """Recursively search a directory for files.

path: directory to search

Attributes:

path: as passed to the constructor

"""

    def __init__ (self, path):
        self.path = os.path.expanduser(path)

    def __iter__ (self):
        # doesn't throw
        join = os.path.join
        for d, dirs, files in os.walk(self.path):
            for f in files:
                yield join(d, f)
