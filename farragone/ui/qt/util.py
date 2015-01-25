"""Farragone Qt UI utilities.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import sys
import os
from multiprocessing import Pipe, Process
from platform import system

from . import qt

_freedesktop = system() != 'Windows'
# contains desktop environment (if any) on freedesktop systems
_desktop_lookup = 'XDG_CURRENT_DESKTOP'


def widget_from_layout (layout):
    """Create empty widget that renders a QLayout."""
    w = qt.QWidget()
    w.setLayout(layout)
    return w


def mk_button (cls, defn):
    """Create a QAbstractButton.

cls: QAbstractButton subclass to use
defn: dict with optional keys:
    text: button label
    icon: standard icon name
    tooltip
    clicked: function to call when the button is clicked

"""
    b = cls()
    if 'text' in defn:
        b.setText(defn['text'])
    if 'icon' in defn:
        b.setIcon(qt.QIcon.fromTheme(defn['icon']))
    if 'tooltip' in defn:
        b.setToolTip(defn['tooltip'])
    if 'clicked' in defn:
        b.clicked.connect(defn['clicked'])
    return b


def add_combobox_items (combobox, *items):
    """Add text items to a QComboBox.

combobox: QComboBox
items: any number of dicts defining items, with keys from Qt.ItemDataRole and
       values the associated data, plus a special (optional) `None` key giving
       generic data for the item (retrieved by QComboBox.currentData())

"""
    for data in items:
        generic_data = data.get(None)
        if generic_data is None:
            combobox.addItem('')
        else:
            combobox.addItem('', generic_data)

        i = combobox.count()
        for role, value in data.items():
            if role is not None:
                combobox.setItemData(i - 1, value, role)


def get_fallback_icon_theme (local_theme, fallback_desktop):
    """Determine a fallback icon theme for DEs Qt doesn't know about.

local_theme: name of the theme to use when the system doesn't understand
             system/user themes - probably distributed with the application
             (path must be added manually)
fallback_desktop: desktop environment to use to determine the fallback theme in
                  some cases (eg. GNOME to use the user's GTK theme) (from
                  http://standards.freedesktop.org/menu-spec/latest/apb.html)

This must be called before creating the Qt application.

Returns the theme name.

"""

    # create a Qt application in a separate process to determine the fallback
    # theme - comes from DE-specific config files
    def get_fallback_theme (pipe):
        os.environ[_desktop_lookup] = fallback_desktop
        app = qt.QApplication([])
        pipe.send(qt.QIcon.themeName())

    if not _freedesktop:
        fallback_theme = local_theme
    elif os.environ.get(_desktop_lookup):
        fallback_theme = None
    else:
        # must do this before creating an application in the main process
        pipe_out, pipe_in = Pipe(duplex=False)
        p = Process(target=get_fallback_theme, args=(pipe_in,))
        p.start()
        p.join()
        fallback_theme = pipe_out.recv()
    return fallback_theme


def apply_fallback_icon_theme (fallback_theme):
    """Apply a fallback icon theme if necessary.

fallback_theme: theme name (probably from `get_fallback_icon_theme`)

This must be called after creating the Qt application.

"""

    def bad_icon_theme (name):
        # if there's no theme name, no lookups are performed
        # hicolor is missing important icons
        return name is None or name == 'hicolor'

    current_theme = qt.QIcon.themeName()
    if bad_icon_theme(current_theme):
        if bad_icon_theme(fallback_theme):
            print('warning: no suitable icon theme found', file=sys.stderr)
        else:
            qt.QIcon.setThemeName(fallback_theme)
