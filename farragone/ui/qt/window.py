"""Farragone Qt UI main window.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from collections import Counter

from .. import conf
from . import qt, widgets, inp, output, run

_lock_messages = {
    'run': 'Cannot quit while renaming is in progress.'
}


class Window (qt.QMainWindow):
    """Main application window."""

    def __init__ (self):
        qt.QMainWindow.__init__(self)
        self.setWindowTitle(conf.APPLICATION)
        # reasons for which this window cannot be closed
        self._locked = Counter()

        out = None
        def changed ():
            if out is not None:
                out.update()
        inputs = inp.Input(self._update_tab_order, changed)
        self.output = out = output.Output(inputs)

        runner = run.Run(inputs)
        runner.started.connect(lambda: self.lock('run'))
        runner.stopped.connect(self._run_stopped)

        layout = qt.QVBoxLayout()
        self.setCentralWidget(widgets.widget_from_layout(layout))
        top = qt.QSplitter(qt.Qt.Horizontal)
        top.setChildrenCollapsible(False)
        layout.addWidget(top, 1)
        top.addWidget(inputs)
        top.addWidget(out)
        layout.addWidget(widgets.widget_from_layout(runner))

        self._update_tab_order()

    def _update_tab_order (self):
        widgets.set_tab_order(
            widgets.natural_widget_order(self.centralWidget()))

    def lock (self, ident):
        # prevent the window from closing
        self._locked[ident] += 1

    def release (self, ident):
        # release a close prevention lock
        self._locked[ident] -= 1

    def _run_stopped (self):
        self.release('run')
        self.output.update()

    def closeEvent (self, evt):
        try:
            ident = next(self._locked.elements())
        except StopIteration:
            # stop preview thread
            self.output.quit()
            evt.accept()
        else:
            evt.ignore()
            msg = _lock_messages[ident]
            qt.QMessageBox.warning(self, conf.APPLICATION, msg)
