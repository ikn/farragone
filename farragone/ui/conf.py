"""Farragone UI configuration.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

IDENTIFIER = 'farragone'
APPLICATION = 'Farragone'
VERSION = '0.1.1-next'

LOG = {
    'qt.widgets.natural_widget_order': False,
    'qt.output:preview': False
}

# minumum interval between Qt signals for potentially rapid emitters
MIN_SIGNAL_INTERVAL = 0.2
# maximum number of renames shown in the preview
MAX_PREVIEW_LENGTH = 500
# used to find an icon theme
FALLBACK_DESKTOP = 'GNOME'
