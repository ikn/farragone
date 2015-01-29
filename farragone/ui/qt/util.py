"""Farragone Qt UI utilities.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import sys
import itertools
from collections import deque
import os
from multiprocessing import Pipe, Process
from platform import system

from .. import conf
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


def _natural_layout_items_order (layout):
    """Return widgets in a layout in order, or None if of unknown type."""
    if isinstance(layout, qt.QBoxLayout):
        return [layout.itemAt(i) for i in range(layout.count())]

    elif isinstance(layout, qt.QGridLayout):
        seen = set()
        items = []
        for r in range(layout.rowCount()):
            for c in range(layout.columnCount()):
                item = layout.itemAtPosition(r, c)
                if item is not None and item not in seen:
                    seen.add(item)
                    items.append(item)
        return items

    else:
        return None


def _natural_widget_widgets_order (widget):
    """Return widgets directly contained in a widget in order, or None."""
    if isinstance(widget, qt.QScrollArea):
        sub_widget = widget.widget()
        return [] if sub_widget is None else [sub_widget]

    elif isinstance(widget, qt.QSplitter):
        return [widget.widget(i) for i in range(widget.count())]

    else:
        return None


def natural_widget_order (*widgets):
    """Return widgets from the given widgets in a natural order.

widgets: top-most widgets to start with, in the desired order

Returns an iterator over bottom-level widgets, going through known layouts and
other widget containers.

"""
    dbg = conf.DEBUG['qt.util.natural_widget_order']
    # contains widgets and layouts
    remain = deque(widgets)
    while remain:
        item = remain.popleft()
        is_widget = isinstance(item, qt.QWidget)
        if is_widget:
            sub_widgets = _natural_widget_widgets_order(item)
            if sub_widgets is None:
                layout = item.layout()
            else:
                if dbg: print('WW', item, '/', sub_widgets)
                remain.extendleft(reversed(sub_widgets))
                # don't check layout
                continue
        else:
            layout = item
        layout_items = _natural_layout_items_order(layout)

        if layout_items is None:
            if is_widget:
                if dbg: print('W', item)
                yield item
        else:
            for layout_item in reversed(layout_items):
                widget = layout_item.widget()

                if widget is None:
                    sub_layout = layout_item.layout()
                    if sub_layout is not None:
                        if dbg: print('WLL', item, '/', layout, '/', sub_layout)
                        remain.appendleft(sub_layout)
                else:
                    if dbg: print('WLW', item, '/', layout, '/', widget)
                    remain.appendleft(widget)


def set_tab_order (widgets):
    """Set the tab order for the given widgets to the given order.

widgets: iterable of widgets

"""
    ws1, ws2 = itertools.tee(widgets, 2)
    # offset the second iterator by one
    next(ws2)
    for w1, w2 in zip(ws1, ws2):
        qt.QWidget.setTabOrder(w1, w2)
