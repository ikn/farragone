"""Farragone Qt UI widget utilities.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import itertools
from collections import deque

from ... import util
from ...conf import settings
from . import qt


def widget_from_layout (layout):
    """Create empty widget that renders a QLayout."""
    w = qt.QWidget()
    w.setLayout(layout)
    return w


def first_layout_widget (layout):
    """Return the first widget in a QLayout, or None."""
    for i in range(layout.count()):
        item = layout.itemAt(0)
        if isinstance(item, qt.QWidgetItem):
            return item.widget()
    else:
        return None


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


def mk_label (text, rich=False, tooltip=None):
    """Create a QLabel.

text: label text
rich: whether to render as rich text (otherwise ignore markup)
tooltip: tooltip text

"""
    label = qt.QLabel()
    label.setTextFormat(qt.Qt.RichText if rich else qt.Qt.PlainText)
    label.setText(text)
    if tooltip is not None:
        label.setToolTip(tooltip)
    return label


def add_combobox_items (combobox, *items):
    """Add text items to a QComboBox.

combobox: QComboBox
items: any number of dicts defining items, with keys from Qt.ItemDataRole and
       values the associated data, plus a special (optional) 'icon' key giving
       the name of the icon to show

"""
    for data in items:
        if 'icon' in data:
            combobox.addItem(qt.QIcon.fromTheme(data['icon']), '')
        else:
            combobox.addItem('')

        i = combobox.count()
        for role, value in data.items():
            if role != 'icon':
                combobox.setItemData(i - 1, value, role)


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


_natural_widget_order_log = util.logger('qt.widgets.natural_widget_order')
def natural_widget_order (*widgets):
    """Return widgets from the given widgets in a natural order.

widgets: top-most widgets to start with, in the desired order

Returns an iterator over bottom-level widgets, going through known layouts and
other widget containers.

"""
    log = _natural_widget_order_log
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
                log('WW', item, '/', sub_widgets)
                remain.extendleft(reversed(sub_widgets))
                # don't check layout
                continue
        else:
            layout = item
        layout_items = _natural_layout_items_order(layout)

        if layout_items is None:
            if is_widget:
                log('W', item)
                yield item
        else:
            for layout_item in reversed(layout_items):
                widget = layout_item.widget()

                if widget is None:
                    sub_layout = layout_item.layout()
                    if sub_layout is not None:
                        log('WLL', item, '/', layout, '/', sub_layout)
                        remain.appendleft(sub_layout)
                else:
                    log('WLW', item, '/', layout, '/', widget)
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


class Window (qt.QMainWindow):
    """A QMainWindow subclass that saves its size.

Takes a string identifier used in the setting keys, followed by any arguments
for QMainWindow.

"""
    def __init__ (self, ident, *args, **kwargs):
        self.ident = ident
        qt.QMainWindow.__init__(self, *args, **kwargs)
        w, h = settings['win_size_{}'.format(ident)][:2]
        self.resize(w, h)
        if settings['win_max_{}'.format(ident)]:
            self.setWindowState(self.windowState() | qt.Qt.WindowMaximized)

    def resizeEvent (self, evt):
        """Save changes to window size."""
        qt.QMainWindow.resizeEvent(self, evt)
        size = evt.size()
        settings['win_size_{}'.format(self.ident)] = (size.width(),
                                                      size.height())

    def changeEvent (self, evt):
        """Save changes to maximised state."""
        qt.QMainWindow.changeEvent(self, evt)
        if evt.type() == qt.QEvent.WindowStateChange:
            old = evt.oldState()
            new = self.windowState()
            is_max = bool(new & qt.Qt.WindowMaximized)

            if bool(old & qt.Qt.WindowMaximized) != is_max:
                settings['win_max_{}'.format(self.ident)] = is_max


class Tab (qt.QObject):
    """Tab representation for use with TabWidget.

name: tab label; may define accelerators using '&'
widget: QWidget to use as the page for the tab
icon: icon name or `None`
closeable: whether the tab has a close button and can be closed

Attributes:

name, widget, closeable: as given
icon: QIcon
error_signal: emitted with the current 'error' state when it changes
new_signal: emitted with the current 'new' state when it changes

"""

    error_signal = qt.pyqtSignal(bool)
    new_signal = qt.pyqtSignal(bool)

    def __init__ (self, name, widget, icon=None, closeable=False):
        qt.QObject.__init__(self)
        self.name = name
        self.widget = widget
        self.icon = qt.QIcon() if icon is None else qt.QIcon.fromTheme(icon)
        self.closeable = closeable
        self._error = False
        self._new = False

    @property
    def error (self):
        """Whether this tab is in an error state."""
        return self._error

    @error.setter
    def error (self, error_state):
        self._error = error_state
        self.error_signal.emit(error_state)

    @property
    def new (self):
        """Whether this tab contains new content."""
        return self._new

    @new.setter
    def new (self, new_state):
        self._new = new_state
        self.new_signal.emit(new_state)


class TabWidget:
    """Tab widget whose tabs are individually closeable and have
error/new states.

Attributes:

widget: QTabWidget; adding tabs directly will not apply correct formatting

"""

    def __init__ (self):
        self.widget = qt.QTabWidget()
        self.widget.setTabsClosable(True)
        self._tabs = {}

    def tab_index (self, tab):
        return self.widget.indexOf(tab.widget)

    def _set_error (self, tab, error_state):
        # update tab formatting to match the given 'error' state
        # QColor() is an invalid colour, which gives the default colour
        colour = qt.QColor(qt.Qt.red) if error_state else qt.QColor()
        self.widget.tabBar().setTabTextColor(self.tab_index(tab), colour)

    def _set_new (self, tab, new_state):
        # update tab formatting to match the given 'new' state
        text = ('* ' if new_state else '') + tab.name
        self.widget.setTabText(self.tab_index(tab), text)

    def _init_new_tab (self, tab):
        # apply initial formatting to an added tab
        i = self.tab_index(tab)
        self.widget.setTabIcon(i, tab.icon)
        if not tab.closeable:
            bar = self.widget.tabBar()
            bar.setTabButton(i, qt.QTabBar.LeftSide, None)
            bar.setTabButton(i, qt.QTabBar.RightSide, None)
        self._set_error(tab, tab.error)
        self._set_new(tab, tab.new)

        tab.error_signal.connect(
            lambda error_state: self._set_error(tab, error_state))
        tab.new_signal.connect(
            lambda new_state: self._set_error(tab, new_state))

    def add (self, tab):
        """Add a new tab to the end of the list.

tab: Tab.

"""
        self.widget.addTab(tab.widget, tab.name)
        self._init_new_tab(tab)
