"""Farragone Qt UI job running.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from html import escape

from ... import core
from . import qt, widgets


class RenameThreadSignals (qt.QObject):
    """Signals for RenameThread."""

    loaded = qt.pyqtSignal()
    start_op = qt.pyqtSignal(int, str, str)
    end_op = qt.pyqtSignal(int, bool, str)


class RenameThread (qt.QRunnable):
    """Thread in which we perform the file renaming.

inputs: inp.Inputs

"""

    def __init__ (self, inputs):
        qt.QRunnable.__init__(self)
        self._inputs = inputs
        self.signals = RenameThreadSignals()

    def run (self):
        """Run rename job.

`start_op` and `end_op` are emitted around each rename, and `loaded` is emitted
when finished.

"""
        inps, fields, transform, template = self._inputs.gather()
        start_op = self.signals.start_op
        end_op = self.signals.end_op

        for i, (frm, to) in enumerate(core.get_renames(
            inps, fields, template, transform
        )):
            start_op.emit(i, frm, to)
            try:
                core.rename(frm, to)
            except OSError as e:
                err = ', '.join(str(arg) for arg in e.args)
            else:
                err = None
            end_op.emit(i, err is not None, err)

        self.signals.loaded.emit()


class Run (qt.QVBoxLayout):
    """Button to do the rename, and display current status.

inputs: inp.Input

Attributes;

started: signal emitted when we start renaming
stopped: signal emitted when we stop renaming
status: QLabel with current status
running: RenameThread or None
current_operation: (frm, to) paths for the current rename, or None
failed: list of error strings for the current/previous run

"""

    started = qt.pyqtSignal()
    stopped = qt.pyqtSignal()

    def __init__ (self, inputs):
        qt.QHBoxLayout.__init__(self)
        self._run_btn = widgets.mk_button(qt.QPushButton, {
            'text': '&Run',
            'icon': 'media-playback-start',
            'tooltip': 'Start the file renaming process',
            'clicked': self.run
        })
        self.addWidget(self._run_btn)
        self.status = widgets.mk_label('', rich=True)
        self.addWidget(self.status)
        self.status.setWordWrap(False)

        self._inputs = inputs
        # not thread-safe, but we only modify it in the main thread
        self.running = None
        self._has_run = False
        self.current_operation = None
        self.failed = []
        self.update_status()

    def status_text (self):
        """Get Qt rich text giving the current status."""
        text = ''
        if self.failed:
            if self.running:
                text += ' <font color="red">[{} failed]</font>'.format(
                    len(self.failed))
            else:
                text += ' <font color="red">{} failed: {}</font>'.format(
                    len(self.failed), self.failed[0])
        elif not self.running:
            text += ' success'

        if self.current_operation is not None:
            frm, to = self.current_operation
            text += escape(' {} → {}'.format(repr(frm), repr(to)))

        if not text:
            text = ' processing...'
        return '<i>{}:{}</i>'.format(
            'Running' if self.running else 'Finished', text)

    def update_status (self):
        """Update display with the current status."""
        if self.running or self._has_run:
            self.status.setText(self.status_text())
            self.status.show()
        else:
            self.status.hide()

    def start_op (self, ident, frm, to):
        """Signal that a rename operation has started.

ident: unique identifier for this operation within the batch
frm: source path
to: destination path

"""
        self.current_operation = (frm, to)
        self.update_status()

    def end_op (self, ident, have_error, error):
        """Signal that a rename operation has finished.

ident: unique identifier for this operation within the batch
have_error: whether the operation failed
error: string error message

"""
        if have_error:
            self.failed.append(error)
        self.current_operation = None
        self.update_status()

    def _end (self):
        """Clean up after running."""
        if self.running:
            self.running = None
            self.update_status()
            self.stopped.emit()
            self._run_btn.setEnabled(True)

    def run (self):
        """Perform the rename operation."""
        if not self.running:
            self._run_btn.setEnabled(False)
            self.started.emit()
            self.running = RenameThread(self._inputs)
            self.current_operation = None
            self.failed = []
            self.running.signals.loaded.connect(self._end)
            self.running.signals.start_op.connect(self.start_op)
            self.running.signals.end_op.connect(self.end_op)

            qt.QThreadPool.globalInstance().start(self.running)
            self._has_run = True
            self.update_status()
