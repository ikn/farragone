"""Farragone Qt UI main window.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from collections import Counter
import webbrowser

from ... import conf
settings = conf.settings
from . import qt, widgets, inp, output, run

_lock_messages = {
    'run': _('Cannot quit while renaming is in progress.')
}


class Window (widgets.Window):
    """Main application window.

paths: sequence of paths to initialise with

"""

    def __init__ (self, paths):
        widgets.Window.__init__(self, 'main')
        self.setWindowTitle(conf.APPLICATION)
        # reasons for which this window cannot be closed
        self._locked = Counter()

        out = None
        init_changed = False
        def changed ():
            if out is None:
                nonlocal init_changed
                init_changed = True
            else:
                out.update()

        self.inputs = inputs = inp.Input(self._update_tab_order, changed)
        self.output = out = output.Output(inputs)
        if init_changed:
            changed()

        runner = run.Run(inputs, out.preview)
        runner.started.connect(self._run_started)
        runner.stopped.connect(self._run_stopped)
        runner.gather_finished.connect(self._run_gather_finished)

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

        inputs.files.add_paths(paths)

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

    def _run_started (self):
        self.lock('run')
        self.inputs.setEnabled(False)

    def _run_gather_finished (self):
        self.inputs.setEnabled(True)

    def _run_stopped (self, started):
        self.release('run')
        # enable inputs here because gather_finished might not always happen
        self.inputs.setEnabled(True)
        if started:
            self.output.update()

    def event (self, evt):
        # gets all events for this widget
        # WhatsThisClicked events propagate up from all child widgets
        if evt.type() == qt.QEvent.WhatsThisClicked:
            webbrowser.open(evt.href())
            evt.accept()
            return True
        else:
            return widgets.Window.event(self, evt)

    def closeEvent (self, evt):
        try:
            ident = next(self._locked.elements())
        except StopIteration:
            # stop preview thread
            self.output.pause()
            evt.accept()
        else:
            evt.ignore()
            msg = _lock_messages[ident]
            qt.QMessageBox.warning(self, conf.APPLICATION, msg)
