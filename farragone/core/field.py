"""Farragone field definitions.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import abc
import itertools
from collections import Counter
import re
from os import path as os_path
import locale

from .. import util


class Context:
    """Collection of functions used to define the part of a path that is
relevant for a field retrieval method."""

    """Whole path."""
    PATH = lambda path: path

    """Path excluding the filename."""
    DIR = lambda path: os_path.dirname(path)

    """Filename."""
    NAME = lambda path: os_path.basename(path)


class Fields (metaclass=abc.ABCMeta):
    """Retrieve fields from a file (abstract base class)."""

    def __or__ (self, other):
        """Combine instances using `FieldCombination`."""
        return FieldCombination(self, other)

    @property
    @abc.abstractmethod
    def names (self):
        """Names of fields that could be returned by `evaluate`."""
        pass

    @property
    def warnings (self):
        """List of util.Warn instances generated from the field source input."""
        warnings = []
        if not all(self.names):
            warnings.append(
                util.Warn('fields', _('empty field name ({})').format(self)))
        return warnings

    @abc.abstractmethod
    def evaluate (self, paths):
        """Retrieve fields from paths.

paths: iterator yielding input paths (absolute and with normalised separators)

Returns an iterator yielding `dict`s with field names as keys and string
values, for each path in `paths`, in the same order.

When fields cannot be retrieved, they are missing from the result.

"""
        pass


class FieldCombination (Fields):
    """Combine field generators so that retrieving fields combines those
retrieved individually.

field_sets: any number of `Fields` instances to combine

Attributes:

field_sets: normalised instances from the `field_sets` argument
duplicate_names: `set` of field names occuring more than once

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
        self._names = list(names.keys())
        self.field_sets = sets if sets else [NoFields()]

        self._warnings = []
        self.duplicate_names = frozenset(+(names - Counter(set(names))))
        if self.duplicate_names:
            detail = _('duplicate field names: {}').format(
                ', '.join(map(repr, self.duplicate_names)))
            self._warnings.append(util.Warn('fields', detail))

    @property
    def names (self):
        return self._names

    @property
    def warnings (self):
        # don't include Fields warnings, since each of field_sets will
        return sum((f.warnings for f in self.field_sets), []) + self._warnings

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

    @property
    def names (self):
        return []

    def evaluate (self, paths):
        for path in paths:
            yield {}


class PathComponent (Fields):
    """Use a path component as a field.

field_name: name to give the retrieved field
index: path component index from 0, negative to index from the end

Attributes:

index: as passed to the constructor

"""

    def __init__ (self, field_name, index=-1):
        self._name = field_name
        index_valid = True
        try:
            self.index = int(index)
        except ValueError:
            index_valid = False
            self.index = -1

        self._warnings = []
        if not index_valid:
            # NOTE: warning detail for invalid path component index
            detail = _('index: {0}, field name: {1}').format(
                repr(index), repr(self._name))
            self._warnings.append(util.Warn('component index', detail))

    def __str__ (self):
        # NOTE: used to refer to a particular field source
        return _('path component, field name: {}').format(repr(self._name))

    @property
    def names (self):
        return [self._name]

    @property
    def warnings (self):
        return Fields.warnings.fget(self) + self._warnings

    def evaluate (self, paths):
        for path in paths:
            # splitdrive always gives path starting with separator
            components = os_path.splitdrive(path)[1].split(os_path.sep)[1:]
            try:
                component = components[self.index]
            except IndexError:
                yield {}
            else:
                yield {self._name: component}


class RegexGroups (Fields):
    """Retrieve fields from groups matched by a regular expression.

pattern: regular expression as a string; not implicitly anchored
field_name_prefix: string giving the prefix for the field name for unnamed
                   groups
context: defines which part of the path to match against

Fields come from groups in `pattern`; groups give field names with prefix
`field_name_prefix` and suffix a number starting at 1, and named groups (eg.
'(?P<name>[0-9]+)') also give fields named like the group.  Fields are missing
for paths not matching `pattern`.

Attributes:

pattern, context: as passed to the constructor
regex: compiled regular expression

"""

    def __init__ (self, pattern, field_name_prefix, context=Context.NAME):
        pattern_err = None
        try:
            regex = re.compile(pattern)
        except re.error as e:
            pattern_err = e
            regex = re.compile('')

        self._field_name_prefix = field_name_prefix
        names = (list(regex.groupindex.keys()) +
                 list(map(self._field_name, range(regex.groups))))
        self._names = set(names)
        self.pattern = pattern
        self.regex = regex
        self.context = context

        self._warnings = []

        if pattern_err is not None:
            # NOTE: warning detail for an invalid regular expression;
            # placeholders are the pattern and the error message
            self._warnings.append(util.Warn('regex', _('{0}: {1}').format(
                repr(pattern), util.exc_str(pattern_err)
            )))

        extra_names = Counter(names) - Counter(set(names))
        if extra_names:
            # NOTE: warning detail for an invalid field source; placeholders are
            # the duplicated field names and a description of the field source
            detail = _(
                'duplicate field names: {0} ({1})'
            ).format(', '.join(map(repr, extra_names.keys())), self)
            self._warnings.append(util.Warn('fields', detail))

    def __str__ (self):
        # NOTE: used to refer to a particular field source
        return _('regular expression, pattern: {}').format(repr(self.pattern))

    @property
    def names (self):
        return self._names

    @property
    def warnings (self):
        return Fields.warnings.fget(self) + self._warnings

    def _field_name (self, idx):
        # get the field name for a group by index
        return self._field_name_prefix + str(idx + 1)

    def evaluate (self, paths):
        for path in paths:
            matches = self.regex.finditer(self.context(path))
            try:
                match = next(matches)
            except StopIteration:
                yield {}
            else:
                fields = {self._field_name(i): field
                          for i, field in enumerate(match.groups())}
                fields.update(match.groupdict())
                yield fields


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

    def __str__ (self):
        # NOTE: used to refer to a particular field source
        return _('ordering, field name: {}').format(repr(self._name))

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
