"""Farragone.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import gettext

from . import coreconf as _conf

gettext.install(_conf.IDENTIFIER, _conf.PATH_LOCALE, names=('ngettext',))

from . import util, conf, core, ui
