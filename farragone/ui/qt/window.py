"""Farragone Qt UI main window.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from collections import Counter

from ... import conf
settings = conf.settings
from . import qt, widgets, inp, output, run

_lock_messages = {
    'run': _('Cannot quit while renaming is in progress.')
}


class Window (widgets.Window):
    """Main application window."""

    def __init__ (self):
        widgets.Window.__init__(self, 'main')
        self.setWindowTitle(conf.APPLICATION)
        # reasons for which this window cannot be closed
        self._locked = Counter()

        out = None
        def changed ():
            if out is not None:
                out.update()
        inputs = inp.Input(self._update_tab_order, changed)
        self.output = out = output.Output(inputs)

        runner = run.Run(inputs, out.preview)
        runner.started.connect(lambda: self.lock('run'))
        runner.stopped.connect(self._run_stopped)

        layout = qt.QVBoxLayout()
        self.setCentralWidget(widgets.widget_from_layout(layout))

        top = qt.QSplitter(qt.Qt.Horizontal)
        top.setChildrenCollapsible(False)
        layout.addWidget(top, 1)
        top.addWidget(inputs)
        top.addWidget(out.widget)
        ratio = int(100 * settings['splitter_ratio_main'])
        top.setStretchFactor(0, ratio)
        top.setStretchFactor(1, 100 - ratio)
        top.splitterMoved.connect(lambda: self._splitter_moved(top))

        layout.addWidget(widgets.widget_from_layout(runner))

        self._update_tab_order()

    def _update_tab_order (self):
        widgets.set_tab_order(
            widgets.natural_widget_order(self.centralWidget()))

    def _splitter_moved (self, splitter):
        # save main splitter ratio on change
        x, y = splitter.sizes()
        settings['splitter_ratio_main'] = x / (x + y)

    def lock (self, ident):
        # prevent the window from closing
        self._locked[ident] += 1

    def release (self, ident):
        # release a close prevention lock
        self._locked[ident] -= 1

    def _run_stopped (self, started):
        self.release('run')
        if started:
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
