"""Farragone Qt UI preview system.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from ... import core
from .. import conf
from . import qt


class Output (qt.QTextEdit):
    """Preview for files to be renamed."""

    def __init__ (self):
        qt.QTextEdit.__init__(self)
        self.setReadOnly(True)
        self.setLineWrapMode(qt.QTextEdit.NoWrap)

    def add_line (self, text):
        """Add a line of text to the display."""
        # don't use QTextEdit.append, since it's not documented whether it
        # accepts HTML or plain text
        self.insertPlainText(text)
        # new line
        self.textCursor().insertBlock()

    def update(self, inputs):
        """Update the preview from the current settings.

inputs: inp.Input

"""
        inps, fields, transform, template = inputs.gather()
        self.setPlainText('')

        for i, (frm, to) in enumerate(core.get_renames(
            inps, fields, template, transform
        )):
            self.add_line('{} → {}'.format(repr(frm), repr(to)))
            if i >= conf.MAX_PREVIEW_LENGTH:
                self.add_line('...')
                break
