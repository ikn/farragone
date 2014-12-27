from abc import abstractmethod
from glob import iglob


class Input:
    """Defines a method for retrieving input paths."""

    @abstractmethod
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
        self.pattern = pattern

    def __iter__ (self):
        return iglob(self.pattern)
