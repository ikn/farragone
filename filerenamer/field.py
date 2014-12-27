from abc import abstractmethod
import itertools
from collections import Counter
from os import path as os_path
import locale


class Context:
    """Collection of functions used to define the part of a path that is
relevant for a field retrieval method."""

    """Whole path."""
    PATH = lambda path: path

    """Path excluding the filename."""
    DIR = lambda path: os_path.dirname(path)

    """Filename."""
    NAME = lambda path: os_path.basename(path)


class Fields:
    """Retrieve fields from a file (abstract base class)."""

    def __or__ (self, other):
        """Combine instances using `FieldCombination`."""
        return FieldCombination(self, other)

    @property
    @abstractmethod
    def names (self):
        """Names of fields that could be returned by `evaluate`."""
        pass

    @abstractmethod
    def evaluate (self, paths):
        """Retrieve fields from paths.

paths: iterator yielding input paths

Returns an iterator yielding `dict`s with field names as keys and string
values, for each path in `paths`, in the same order.

"""
        pass


class FieldCombination (Fields):
    """Combine field generators so that retrieving fields combines those
retrieved individually.

field_sets: any number of `Fields` instances to combine

Constructor throws `ValueError` if any instances in `field_sets` may generate
fields with the same name.

Attributes:

field_sets: normalised instances from the `field_sets` argument

"""

    def __init__ (self, *field_sets):
        sets = []

        for fields in field_sets:
            if isinstance(fields, FieldCombination):
                sets.extend(fields.field_sets)
            else:
                sets.append(fields)

        names = Counter(itertools.chain.from_iterable(
            fields.names for fields in sets))
        extra_names = +(names - Counter(set(names)))
        if extra_names:
            raise ValueError('cannot combine field sets: duplicate names',
                             extra_names)

        self.field_sets = sets

    def evaluate (self, paths):
        path_iters = itertools.tee(paths, len(self.field_sets))

        for results in zip(*(
            fields.evaluate(path_iter)
            for fields, path_iter in zip(self.field_sets, path_iters)
        )):
            combined_result = {}
            for result in results:
                combined_result.update(result)
            yield combined_result


class NoFields (Fields):
    """Always retrieve an empty `dict` of fields."""

    def evaluate (self, paths):
        for path in paths:
            yield {}


class RegexGroups (Fields):
    """Retrieve fields from groups matched by a regular expression.

pattern: compiled regular expression (returned by `re.compile`); not implicitly
         anchored
context: defines which part of the path to match against

Fields come from named groups in `pattern` (eg. '(?P<name>[0-9]+)').  Fields
are missing for paths not matching `pattern`.

Attributes:

pattern, context: as passed to the constructor

"""

    def __init__ (self, pattern, context=Context.NAME):
        self._names = list(pattern.groupindex.keys())
        self.pattern = pattern
        self.context = context

    @property
    def names (self):
        return self._names

    def evaluate (self, paths):
        for path in paths:
            matches = self.pattern.finditer(self.context(path))
            try:
                match = next(matches)
            except StopIteration:
                yield {}
            else:
                yield match.groupdict()


class Ordering (Fields):
    """Sort paths and use their position as a field.

field_name: name to give the retrieved field
key: standard 'key function' for sorting
reverse: whether to reverse the sort order
context: defines which part of the path to pass to `key`

The field value is a number starting at 1 (as a string).

Attributes:

key, reverse, context: as passed to the constructor

"""

    def __init__ (self, field_name, key=locale.strxfrm, reverse=False,
                  context=Context.NAME):
        self._name = field_name
        self.key = key
        self.reverse = reverse
        self.context = context

    @property
    def names (self):
        return [self._name]

    def evaluate (self, paths):
        get_key = self.key
        context = self.context

        ordered = sorted(enumerate(map(context, paths)),
                         key=lambda x: get_key(x[1]), reverse=self.reverse)
        with_order = sorted(enumerate(ordered), key=lambda x: x[1][0])
        for sorted_index, (orig_index, path) in with_order:
            yield {self._name: str(sorted_index + 1)}
