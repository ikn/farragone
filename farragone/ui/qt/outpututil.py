"""Farragone Qt UI output section.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from html import escape

from . import qt, widgets


class States:
    # labels for the 'state' field
    # NOTE: status text indicating no processing is happening
    idle = _('idle')
    # NOTE: status text indicating processing is happening
    busy = _('processing...')


class StatusField (qt.QLabel):
    """A field in the status bar of a `Section`.

render: a function taking a single argument and returning plain text to display
value: argument to pass to `render` to initialise the display

"""

    def __init__ (self, render='{}'.format, value=''):
        self._render = render
        qt.QLabel.__init__(self)
        self.setTextFormat(qt.Qt.RichText)
        self.update(value)

    def update (self, value):
        """Update the display by passing the given value to the `render`
function."""
        self.setText('<i>{}</i>'.format(escape(self._render(value))))


def num_files_field ():
    """Create a `StatusField` displaying a number of files.

The value used for rendering is the number.

"""
    # NOTE: display of number of files processed so far in the preview
    render = lambda num: ngettext('{} file', '{} files', num).format(num)
    return StatusField(render, 0)


class Section (widgets.Tab):
    """A section in the output region of the UI."""

    def __init__ (self, name, widget, *args, **kwargs):
        layout = qt.QVBoxLayout()
        widgets.Tab.__init__(self, name, widgets.widget_from_layout(layout),
                             *args, **kwargs)
        layout.addWidget(widget, 1)
        self._empty = True # whether there are no status fields
        self._status = qt.QStatusBar()
        layout.addWidget(self._status)

        self._busy = False
        self._state = StatusField(value=States.idle)
        self.add_status_field(self._state)

    def add_status_field (self, field):
        """Add a `StatusField` to the section's status bar."""
        if not self._empty:
            self._status.addWidget(widgets.sep(qt.QFrame.VLine))
        self._status.addWidget(field)
        self._empty = False

    def _set_working (self, working):
        self._state.update(States.busy if working else States.idle)

    """Set the state of this section so that it is busy or idle."""
    working = property(fset=_set_working)
