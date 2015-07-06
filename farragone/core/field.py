"""Farragone field definitions.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import abc
import itertools
from collections import Counter
import math
import re
from os import path as os_path
import locale

from .. import util
from . import db


class Alignment:
    """Definition of the alignment of a string when formatting with padding.

name: alignment display name
fmt: character for use in a string formatting specification

Attributes:

name, fmt: as passed to the constructor

"""

    def __init__ (self, name, fmt):
        self.name = name
        self.fmt = fmt


# `Alignment` instances enum
class Alignments:
    # NOTE: padding alignment option
    right = Alignment(_('Right'), '>')
    # NOTE: padding alignment option
    left = Alignment(_('Left'), '<')
    # NOTE: padding alignment option
    centre = Alignment(_('Center'), '^')


# sequence of `Alignment` instances, ordered by importance
all_alignments = (Alignments.right, Alignments.left, Alignments.centre)


_sort_numeric_pattern = re.compile(r'-?\d+(\.\d+)?')
# key function for 'Numeric' sort type
def _sort_numeric (s):
    match = _sort_numeric_pattern.search(s)
    # no math.inf until 3.5
    return (float('inf') if match is None
            else float(match.group(0)))


_sort_version_pattern = re.compile(r'\d+(\.\d+)*')
# key function for 'Version' sort type
def _sort_version (s):
    match = _sort_version_pattern.search(s)
    # no math.inf until 3.5
    return ((float('inf'),) if match is None
            else tuple(map(int, match.group(0).split('.'))))


class SortType:
    """Definition of a method of ordering strings.

name: sort type display name
key: standard 'key function' for sorting
desc: short description

Maybe be called as a key function.

Attributes:

name, desc: as passed to the constructor

"""

    def __init__ (self, name, key, desc=None):
        self.name = name
        self._key = key
        self.desc = desc

    def __call__ (self, s):
        return self._key(s)


# `SortType` instances enum
class SortTypes:
    # NOTE: sort type option
    alphabetical = SortType(_('Alphabetical'), locale.strxfrm)
    # NOTE: sort type option
    numeric = SortType(_('Numeric'), _sort_numeric)
    # NOTE: sort type option
    version = SortType(_('Version'), _sort_version,
                       # NOTE: description for the 'Version' sort type option
                       _('For example: 0.9 or 3.1.4'))


# sequence of `SortType` instances, ordered by importance
all_sort_types = (SortTypes.alphabetical, SortTypes.numeric, SortTypes.version)


class Context:
    """Definition of a function used to define the part of a path that is
relevant for a field retrieval method.

name: context display name
f: function to be called with a path to retrieve the relevant part
desc: full description of the context

May be called with a path to return the relevant part.

Attributes:

name, desc: as passed to the contstructor

"""

    def __init__ (self, name, f, desc):
        self.name = name
        self.desc = desc
        self._f = f

    def __call__ (self, path):
        return self._f(path)


# `Context` instances enum
class Contexts:
    # NOTE: as in file path
    PATH = Context(_('Path'), lambda path: path,
                   # NOTE: as in file path
                   _('The full path'))
    # NOTE: as in file/directory name
    NAME = Context(_('Name'), lambda path: os_path.basename(path),
                   _('Just the name of the file or directory'))
    DIR = Context(_('Directory'), lambda path: os_path.dirname(path),
                  _('The path excluding the filename'))


# sequence of `Context` instances, ordered by importance
all_contexts = (Contexts.NAME, Contexts.PATH, Contexts.DIR)


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
    def evaluate (self, paths, interrupt=None):
        """Retrieve fields from paths.

paths: iterator yielding input paths (absolute and with normalised separators)
interrupt: abort when this function returns True

Returns an `(results, state)` where:

results: iterator yielding `(path, fields)` tuples, where `path` is the original
         path (order is preserved as in `paths`), and `fields` is a `dict` with
         field names as keys and string values
state: should be passed to `cleanup` once `results` has been used

When fields cannot be retrieved, they are missing from the result.

"""
        pass

    @abc.abstractmethod
    def cleanup (self, state):
        """Clean up state returned by `evaluate`."""
        pass


class SimpleEvalFields (Fields, metaclass=abc.ABCMeta):
    """Fields where evaluation is independent for each path."""

    @abc.abstractmethod
    def evaluate_one (self, path):
        """Return a `dict` of fields for the given path."""
        pass

    def evaluate (self, paths, interrupt=None):
        eval_one = self.evaluate_one
        return (((path, eval_one(path)) for path in paths), None)

    def cleanup (self, state):
        pass


class ComplexEvalFields (Fields, metaclass=abc.ABCMeta):
    """Fields where evaluation for a path may depend on other paths."""

    @abc.abstractmethod
    def init_store (self):
        """Initialise any storage necessary for evaluation and return it.

This is passed to `cleanup` once finished.

"""
        pass

    @abc.abstractmethod
    def store_one (self, state, path):
        """Store any information necessary about a path for evaluating fields
for it later.

state: as returned by `init_store`
path: absolute source path

"""
        pass

    def store (self, paths):
        """Set up storage and store information for all paths.

paths: iterator over source paths.

"""
        state = self.init_store()
        store_one = self.store_one
        return ((store_one(state, path) for path in paths), state)

    @abc.abstractmethod
    def evaluate_stored (self, state):
        """Compute fields for all paths passed to `store_one`.

Returns an iterator like `results` returned by `evaluate`, with paths in the
order passed to `store` (the order of calls to `store_one`).

"""
        pass

    def evaluate (self, paths, interrupt=None):
        store_iter, state = self.store(paths)
        util.consume(store_iter, interrupt)
        return (self.evaluate_stored(), state)


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

    def evaluate (self, paths, interrupt=None):
        cplx = [fields for fields in self.field_sets
                if isinstance(fields, ComplexEvalFields)]
        simple = [fields for fields in self.field_sets
                  if not isinstance(fields, ComplexEvalFields)]
        states = {}

        # sets path_vals
        if cplx:
            cplx_path_iters = itertools.tee(paths, len(cplx))
            store_iters = []
            for fields, path_iter in zip(cplx, cplx_path_iters):
                store_iter, state = fields.store(path_iter)
                store_iters.append(store_iter)
                states[fields] = state
            util.consume(zip(*store_iters), interrupt)

            first = cplx.pop()
            path_vals = first.evaluate_stored(states[first])

        else:
            path_vals = ((path, {}) for path in paths)

        # sets first_path_vals, simple_results
        if simple:
            first_path_vals, simple_path_vals = itertools.tee(path_vals, 2)
            path_iters = itertools.tee((path for path, val in simple_path_vals),
                                       len(simple))
            simple_results = []
            for fields, path_iter in zip(simple, path_iters):
                single_results, state = fields.evaluate(path_iter)
                simple_results.append(single_results)
                states[fields] = state

        else:
            first_path_vals = path_vals
            simple_results = []

        cplx_results = [fields.evaluate_stored(states[fields])
                        for fields in cplx]

        def get ():
            for results in zip(first_path_vals,
                               *(simple_results + cplx_results)):
                combined_result = {}
                for path, result in results:
                    combined_result.update(result)
                yield (results[0][0], combined_result)

        return (get(), states)

    def cleanup (self, states):
        for fields, state in states.items():
            fields.cleanup(state)


class NoFields (SimpleEvalFields):
    """Always retrieve an empty `dict` of fields."""

    @property
    def names (self):
        return []

    def evaluate_one (self, path):
        return {}


class PathComponent (SimpleEvalFields):
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

    def evaluate_one (self, full_path):
        drive, path = os_path.splitdrive(full_path)
        components = [drive]
        # absolute, so splitdrive always gives path starting with separator
        components.extend(path.split(os_path.sep)[1:])
        try:
            component = components[self.index]
        except IndexError:
            return {}
        else:
            return {self._name: component}


class RegexGroups (SimpleEvalFields):
    """Retrieve fields from groups matched by a regular expression.

pattern: regular expression as a string; not implicitly anchored
field_name_prefix: string giving the prefix for the field name for unnamed
                   groups
context: `Context` defining which part of the path to match against

Matching is case-insensitive.

Fields come from groups in `pattern`; groups give field names with prefix
`field_name_prefix` and suffix a number starting at 1, and named groups (eg.
'(?P<name>[0-9]+)') also give fields named like the group.  The whole pattern
gives a field with name `field_name_prefix`.  Fields are missing for paths not
matching `pattern`.

Attributes:

pattern, context: as passed to the constructor
regex: compiled regular expression

"""

    def __init__ (self, pattern, field_name_prefix, context=Contexts.NAME):
        pattern_err = None
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            pattern_err = e
            regex = re.compile('')

        self._field_name_prefix = field_name_prefix
        names = list(map(self._field_name, range(regex.groups)))
        # no fields for positional groups if prefix is empty
        if field_name_prefix:
            names.append(field_name_prefix)
            names.extend(regex.groupindex.keys())
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

    def evaluate_one (self, path):
        matches = self.regex.finditer(self.context(path))
        try:
            match = next(matches)
        except StopIteration:
            return {}
        else:
            fields = {}
            if self._field_name_prefix:
                fields.update({self._field_name(i): field
                               for i, field in enumerate(match.groups())})
                try:
                    fields[self._field_name_prefix] = match.group(0)
                except IndexError:
                    pass
            fields.update(match.groupdict())
            return fields


class Ordering (ComplexEvalFields):
    """Sort paths and use their position as a field.

field_name: name to give the retrieved field
key: standard 'key function' for sorting (see `SortTypes` for some
     implementations)
reverse: whether to reverse the sort order
context: `Context` defining which part of the path to pass to `key`
fmt: function to use to format the ordered index to generate the string field
     value

The field value is a number starting at 1 (after running through `fmt`).

Attributes:

key, reverse, context, fmt: as passed to the constructor

"""

    def __init__ (self, field_name, key=SortTypes.alphabetical, reverse=False,
                  context=Contexts.NAME, fmt=str):
        self._name = field_name
        self.key = key
        self.reverse = reverse
        self.context = context
        self.fmt = fmt

    def __str__ (self):
        # NOTE: used to refer to a particular field source
        return _('ordering, field name: {}').format(repr(self._name))

    @staticmethod
    def auto_padding_size (inps, interrupt=None):
        """Determine what the ideal padding size is.

inps: sequence of `inputs.Input`
interrupt: abort when this function returns True

Returns a number for using as the `size` argument to `padding_fmt`.

"""
        num = 0
        for path in itertools.chain.from_iterable(inps):
            num += 1
            if interrupt is not None and interrupt():
                return 0
        return 1 if num == 0 else int(math.log10(num) + 1)

    @staticmethod
    def padding_fmt (char='0', align=Alignments.right, size=3):
        """Make a formatting function that adds padding to the ordered index.

char: character used to pad the number (string must have length 1)
align: `Alignment` instance used to determine the position of the number within
       the padded string
size: minimum number of characters in the padded string (greater than 0)

For use as the `fmt` argument to the constructor

"""
        return ('{:' + '{}{}{}'.format(char, align.fmt, size) + '}').format

    @property
    def names (self):
        return [self._name]

    def init_store (self):
        return db.OrderingDB(self.key, self.reverse)

    def store_one (self, odb, path):
        odb.add(self.context(path), path)

    def evaluate_stored (self, odb):
        odb.sort()
        fmt = self.fmt
        for index, path in odb.get_sorted():
            yield (path, {self._name: fmt(index)})

    def cleanup (self, odb):
        odb.close()
