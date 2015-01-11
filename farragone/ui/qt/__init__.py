"""Farragone Qt UI.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from .. import conf
from . import qt, util, inp, output, run


class Window (qt.QMainWindow):
    """Main application window."""

    def __init__ (self):
        qt.QMainWindow.__init__(self)
        self.setWindowTitle(conf.APPLICATION)

        out = output.Output()
        def changed ():
            out.update(inputs)
        inputs = inp.Input(changed)

        layout = qt.QVBoxLayout()
        self.setCentralWidget(util.widget_from_layout(layout))
        top = qt.QSplitter(qt.Qt.Horizontal)
        top.setChildrenCollapsible(False)
        layout.addWidget(top, 1)
        top.addWidget(inputs)
        top.addWidget(out)
        layout.addWidget(util.widget_from_layout(run.Run(inputs)))
