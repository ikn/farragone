"""Farragone Qt UI output section.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from . import qt, widgets, preview


class Output (widgets.TabWidget):
    """Output region of the UI.

inputs: inp.Input

"""

    def __init__ (self, inputs):
        widgets.TabWidget.__init__(self)
        self.widget.setTabPosition(qt.QTabWidget.East)
        # don't need extra borders since tab widgets have borders
        self.widget.setDocumentMode(True)
        self.widget.tabBar().setDrawBase(False)
        # results tabs start with the identifier
        self.widget.setElideMode(qt.Qt.ElideRight)

        self.preview = preview.Preview(inputs)
        self.add(self.preview.renames)
        #self.add(self.preview.warnings)

    def update (self):
        """Update the preview tabs from the input section."""
        self.preview.update()

    def quit (self):
        """Stop any background tasks and don't allow any more to start."""
        self.preview.quit()
