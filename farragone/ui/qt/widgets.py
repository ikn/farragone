"""Farragone Qt UI widget utilities.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import itertools
from collections import deque

from .. import util
from . import qt


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