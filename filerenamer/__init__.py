import itertools
from os import path as os_path

from . import inputs, field, qt



def _get_abs_path (path, cwd=None):
    """Make a path absolute.

path: relative or absolute path
cwd: directory that `path` is relative to (default: Python process's current
     working directory)

"""
    abs_path = os_path.abspath(path)
    return (
        os_path.normpath(os_path.join(cwd, path))
        if cwd is not None and abs_path != path
        else abs_path
    )


# returns abs paths
# fields: Fields
# template: string.Template
# fields_transform: dict -> dict
# cwd: str=os.getcwd()
def get_renames (inps, fields, template, fields_transform=lambda f: f,
                 cwd=None):
    """Get files to rename and destination paths.

inps: sequence of `inputs.Input` to retrieve paths from
fields: `field.Fields` instance defining fields to retrieve from input paths
template: `string.Template` instance to generate output paths using retrieved
          fields
fields_transform: function taking a fields `dict` and producing another
cwd: directory that relative paths are relative to

Returns an iterator yielding `(input_path, output_path)` pairs, where both
paths are absolute.

"""
    if cwd is not None:
        cwd = os_path.abspath(cwd)

    paths = itertools.chain.from_iterable(inps)
    abs_paths = map(lambda path: _get_abs_path(path, cwd), paths)
    paths1, paths2 = itertools.tee(abs_paths, 2)

    for path, field_vals in zip(
        paths2, map(fields_transform, fields.evaluate(paths1))
    ):
        yield (path, _get_abs_path(template.safe_substitute(field_vals), cwd))
