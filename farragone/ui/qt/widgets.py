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


class ActionButton (qt.QPushButton):
    """Create a `QPushButton` from a `QAction`.

action: `QAction` to use; the button updates when the action is changed
skip: behaviour to ignore when creating the button; a sequence of strings, each
      one of 'text', 'statustip', 'tooltip', 'icon', 'enabled', 'checkable' and
      'checked'

"""

    def __init__ (self, action, skip=()):
        self._action = action
        self._skip = frozenset(skip)
        qt.QPushButton.__init__(self)
        action.changed.connect(self._update_from_action)
        self.clicked.connect(action.trigger)
        self._update_from_action()

    def _update_from_action (self):
        skip = self._skip
        if 'text' not in skip:
            self.setText(self._action.text())
        if 'statustip' not in skip:
            self.setStatusTip(self._action.statusTip())
        if 'tooltip' not in skip:
            self.setToolTip(self._action.toolTip())
        if 'icon' not in skip:
            self.setIcon(self._action.icon())
        if 'enabled' not in skip:
            self.setEnabled(self._action.isEnabled())
        if 'checkable' not in skip:
            self.setCheckable(self._action.isCheckable())
        if 'checked' not in skip:
            self.setChecked(self._action.isChecked())


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
icon: icon name
doc: help string (Qt rich text)
closeable: whether the tab has a close button and can be closed

Attributes:

name, widget, doc, closeable: as given
icon: QIcon
error_signal: emitted with the current 'error' state when it changes
new_signal: emitted with the current 'new' state when it changes

"""

    error_signal = qt.pyqtSignal(bool)
    new_signal = qt.pyqtSignal(bool)

    def __init__ (self, name, widget, icon=None, doc=None, closeable=False):
        qt.QObject.__init__(self)
        self.name = name
        widget._tab = self
        self.widget = widget
        self.icon = qt.QIcon() if icon is None else qt.QIcon.fromTheme(icon)
        self.doc = doc
        if doc is not None:
            widget.setWhatsThis(doc)
        self.closeable = closeable
        self._error = False
        self._new = False

    @staticmethod
    def from_page (widget):
        # get a Tab given the widget used as its page
        return widget._tab

    @property
    def error (self):
        """Whether this tab is in an error state."""
        return self._error

    @error.setter
    def error (self, error_state):
        if error_state != self._error:
            self._error = error_state
            self.error_signal.emit(error_state)

    @property
    def new (self):
        """Whether this tab contains new content."""
        return self._new

    @new.setter
    def new (self, new_state):
        if new_state != self._new:
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
        self.widget.currentChanged.connect(self._current_changed)
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
        i = self.tab_index(tab)
        if new_state and i == self.widget.currentIndex():
            # shouldn't make it new, and shouldn't think it's new
            tab.new = False
        else:
            text = ('* ' if new_state else '') + tab.name
            self.widget.setTabText(i, text)

    def _current_changed (self, i):
        # current tab changed to index i
        Tab.from_page(self.widget.widget(i)).new = False

    def _init_new_tab (self, tab):
        # apply initial formatting to an added tab
        i = self.tab_index(tab)
        self.widget.setTabIcon(i, tab.icon)
        if not tab.closeable:
            bar = self.widget.tabBar()
            bar.setTabButton(i, qt.QTabBar.LeftSide, None)
            bar.setTabButton(i, qt.QTabBar.RightSide, None)
        if tab.doc is not None:
            bar.setTabWhatsThis(i, tab.doc)
        self._set_error(tab, tab.error)
        self._set_new(tab, tab.new)

        tab.error_signal.connect(
            lambda error_state: self._set_error(tab, error_state))
        tab.new_signal.connect(
            lambda new_state: self._set_new(tab, new_state))

    def add (self, tab):
        """Add a new tab to the end of the list.

tab: Tab.

"""
        self.widget.addTab(tab.widget, tab.name)
        self._init_new_tab(tab)


def question (msg, btns, parent=None, default=None, warning=False,
              ask_again=None):
    """Show a dialogue asking a question.

question(msg, btns[, parent][, default], warning=False[, ask_again])
    -> response

msg: text to display; just a string or (primary, secondary).
btns: a list of actions to present as buttons, where each is a
      QMessageBox.StandardButton, or (text[, icon], role) where:
    text: button text (with '&' accelerator marker)
    icon: freedesktop icon name
    role: QMessageBox.ButtonRole
parent: dialogue parent.
default: the index of the button in btns that should be selected by default.
         If None or not given, there is no default.
warning: whether this is a warning dialogue (instead of just a question).
ask_again: show a 'Don't ask again' checkbox.  This is
           `(setting_key, match_response)`, such that if the checkbox is ticked
           and `response` is `match_response`, `setting_key` is added to the
           'disabled_warnings' setting.

response: The index of the selected button in btns.

"""
    if ask_again is not None and ask_again[0] in settings['disabled_warnings']:
        return ask_again[1]

    if isinstance(msg, str):
        msg = (msg,)
    d = qt.QMessageBox(parent)
    d.setIcon(qt.QMessageBox.Warning if warning else qt.QMessageBox.Question)
    d.setTextFormat(qt.Qt.PlainText)
    d.setText(msg[0])
    if len(msg) >= 2:
        d.setInformativeText(msg[1])

    def fail_ask_again ():
        util.warn(_('hacky implementation of \'ask again\' found unexpected '
                    'dialogue layout; refusing to continue'))
        nonlocal ask_again
        ask_again = None


    # add checkbox (HACK)
    grid = d.layout()
    num_cols = 3
    num_rows = 3
    checkbox_col = 2
    checkbox_row = (num_rows - 1) if len(msg) >= 2 else (num_rows - 2)

    if ask_again is not None:
        # check it'll still work in this version of qt
        if (not isinstance(grid, qt.QGridLayout) or
            grid.columnCount() != num_cols or grid.rowCount() != num_rows):
            fail_ask_again()


    if ask_again is not None and checkbox_row == num_rows - 1:
        # move buttons down to make a row for the checkbox
        to_add = []
        from_row = checkbox_row
        to_row = from_row + 1

        for col in range(3):
            w = grid.itemAtPosition(from_row, col)
            if isinstance(w, qt.QWidgetItem):
                to_add.append((col, w))
            elif w is not None:
                # don't know what to do with this
                fail_ask_again()
                break

        if ask_again is not None:
            for col, w in to_add:
                grid.addWidget(w.widget(), to_row, col)

    if ask_again is not None:
        c = qt.QCheckBox(_('&Don\'t ask again'))
        grid.addWidget(c, checkbox_row, checkbox_col)


    response_map = {}
    for i, data in enumerate(btns):
        if isinstance(data, (tuple, list)):
            # (text[, icon], role)
            btn = qt.QPushButton(data[0])
            if len(data) == 3:
                btn.setIcon(qt.QIcon.fromTheme(data[1]))
            add_args = (btn, data[-1])
        else:
            # standard button
            add_args = (data,)

        btn = d.addButton(*add_args) or btn
        response_map[btn] = i
        if i == default:
            d.setDefaultButton(btn)
        # disable auto-default for every button, so that default=None works
        btn.setAutoDefault(False)

    d.exec()
    response = response_map[d.clickedButton()]

    if ask_again is not None:
        # handle checkbox value
        setting_key, match_response = ask_again
        if c.isChecked() and response == match_response:
            settings['disabled_warnings'] |= {setting_key}

    return response
