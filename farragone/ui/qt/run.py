# coding=utf-8
"""Farragone Qt UI job running.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from html import escape

from ... import core, util
from . import qt, widgets, sync


class RunState:
    """The current state of the renaming process."""
    idle = 0
    preparing = 1
    running = 2
    paused = 3


class RenameThreadSignals (qt.QObject):
    """Signals for RenameThread."""

    start_op = qt.pyqtSignal(int, str, str)
    end_op = qt.pyqtSignal(int, bool, str)


class RenameThread (sync.PauseableThread):
    """Thread in which we perform the file renaming.

inputs: inp.Inputs

"""

    def __init__ (self, inputs):
        sync.PauseableThread.__init__(self)
        self._inputs = inputs
        self.signals = RenameThreadSignals()

    def run (self):
        """Run rename job.

`start_op` and `end_op` are emitted around each rename.

"""
        def interrupted ():
            self.wait_paused()
            return self.isInterruptionRequested()

        inps, field_sets, template, options = self._inputs.gather(interrupted)
        fields = core.field.FieldCombination(*field_sets)
        start_op = self.signals.start_op
        end_op = self.signals.end_op

        renames, done = core.rename.get_renames(
            inps, fields, template, options.cwd, interrupted)
        copy = options.copy
        for i, (frm, to) in enumerate(renames):
            start_op.emit(i, frm, to)
            try:
                core.rename.rename(frm, to, options.copy)
            except OSError as e:
                err = util.exc_str(e)
            else:
                err = None
            end_op.emit(i, err is not None, err)

            if interrupted():
                break
        done()


class Run (qt.QVBoxLayout):
    """Button to do the rename, and display current status.

inputs: inp.Input
preview: preview.Preview

Attributes;

started: signal emitted when we start renaming
stopped: signal emitted when we stop renaming; argument indicates whether
         renaming actually started
gather_finished: signal emitted when we've finished gathering data from `inputs`
status: QLabel with current status
state: from RunState
current_operation: (frm, to) paths for the current rename, or None
failed: list of error strings for the current/previous run

"""

    started = qt.pyqtSignal()
    stopped = qt.pyqtSignal(bool)
    gather_finished = qt.pyqtSignal()

    def __init__ (self, inputs, preview):
        qt.QHBoxLayout.__init__(self)
        self._run_btn = widgets.mk_button(qt.QPushButton, {
            # NOTE: & marks the keyboard accelerator
            'text': _('&Run'),
            'icon': 'media-playback-start',
            'tooltip': _('Start the file renaming process'),
            'clicked': self.run
        })
        self.addWidget(self._run_btn)

        status_line = qt.QHBoxLayout()
        self.addLayout(status_line)
        status_line.addWidget(
            widgets.ActionButton(qt.QWhatsThis.createAction(), skip=('text',)))
        self.status = widgets.mk_label('', rich=True)
        self.status.setWordWrap(False)
        status_line.addWidget(self.status, stretch=1)

        self._btns = {
            'skip': widgets.mk_button(qt.QPushButton, {
                # NOTE: & marks the keyboard accelerator
                'text': _('&Skip'),
                'icon': 'media-skip-forward',
                'clicked': self._continue_run
            }),
            'pause': widgets.mk_button(qt.QPushButton, {
                # NOTE: & marks the keyboard accelerator
                'text': _('Pa&use'),
                'icon': 'media-playback-pause',
                'clicked': self._pause_run
            }),
            'resume': widgets.mk_button(qt.QPushButton, {
                # NOTE: & marks the keyboard accelerator
                'text': _('&Resume'),
                'icon': 'media-playback-start',
                'clicked': self._resume_run
            }),
            'cancel': widgets.mk_button(qt.QPushButton, {
                # NOTE: & marks the keyboard accelerator
                'text': _('&Cancel'),
                'icon': 'process-stop',
                'clicked': self._cancel_run
            })
        }
        # add buttons in a specific order
        for b in (
            self._btns['skip'], self._btns['pause'], self._btns['resume'],
            self._btns['cancel']
        ):
            status_line.addWidget(b)

        self._inputs = inputs
        self._preview = preview
        # not thread-safe, but we only modify it in the main thread
        self.state = RunState.idle
        self._thread = None
        self.current_operation = None
        self._gather_finished_emitted = False
        self.failed = []
        self.update_status()

    def _failed_status (self, abbrev):
        """Get status text showing failures.

abbrev: abbreviated text, without failure reasons

"""
        if abbrev:
            failed_msg = ngettext(
                # NOTE: placeholder is the number of failed operations
                '{} failed', '{} failed', len(self.failed)
            ).format(len(self.failed))
            return '<font color="red">[{}]</font>'.format(failed_msg)
        else:
            failed_msg = ngettext(
                # NOTE: placeholders are the number of failed operations and the
                # failure reason
                '{} failed: {}', '{} failed: {}', len(self.failed)
            ).format(len(self.failed), self.failed[0])
            return '<font color="red">{}</font>'.format(failed_msg)

    def _op_status (self):
        return escape(core.rename.preview_rename(*self.current_operation))

    def _running_status (self):
        """Get status text for when running."""
        msgs = []
        if self.failed:
            msgs.append(self._failed_status(abbrev=True))
        if self.current_operation is not None:
            msgs.append(self._op_status())

        # NOTE: status text
        return ' '.join(msgs) if msgs else _('processing...')

    def status_text (self):
        """Get Qt rich text giving the current status."""
        state = self.state

        if state == RunState.idle:
            # NOTE: status line
            self._running_status()
            msg = (_('Idle: {}').format(self._failed_status(abbrev=False))
                   # NOTE: status line
                   if self.failed else _('Idle'))
        elif state == RunState.preparing:
            # NOTE: status line
            msg = _('Checking for problems...')
        elif state == RunState.running:
            msg = _('Running: {}').format(self._running_status())
        elif state == RunState.paused:
            # NOTE: status line
            msg = _('Paused: {}').format(self._running_status())

        return '<i>{}</i>'.format(msg)

    def update_status (self):
        """Update display with the current status."""
        self.status.setText(self.status_text())

        state = self.state
        for b, visible in (
            (self._btns['skip'], state == RunState.preparing),
            (self._btns['pause'], state == RunState.running),
            (self._btns['resume'], state == RunState.paused),
            (self._btns['cancel'], state != RunState.idle)
        ):
            b.show() if visible else b.hide()

    def start_op (self, ident, frm, to):
        """Signal that a rename operation has started.

ident: unique identifier for this operation within the batch
frm: source path
to: destination path

"""
        if not self._gather_finished_emitted:
            self.gather_finished.emit()
            self._gather_finished_emitted = True
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

    def _end (self, started):
        """Clean up after running.

started: whether renaming actually started (a rename could have been performed)

"""
        if self.state != RunState.idle:
            self.state = RunState.idle
            self._thread = None
            self.update_status()
            self._preview.resume()
            self.stopped.emit(started)
            self._run_btn.setEnabled(True)

    def _pause_run (self):
        """Pause the renaming process if running."""
        if self.state == RunState.running:
            self._thread.paused = True
            self.state = RunState.paused
            self.update_status()

    def _resume_run (self):
        """Resume the renaming process if paused."""
        if self.state == RunState.paused:
            self._thread.paused = False
            self.state = RunState.running
            self.update_status()

    def _cancel_run (self):
        """Cancel the renaming process if preparing or running."""
        state = self.state
        if state == RunState.preparing:
            self._end(False)
        elif (state in (RunState.running, RunState.paused) and
              self._thread is not None):
            if state == RunState.paused:
                self._thread.paused = False
            self._thread.requestInterruption()

    def _continue_run (self):
        """Continuation of `run` - called once a preview is ready."""
        if not self.state == RunState.preparing:
            return
        self.state = RunState.running
        do_run = True

        if self._preview.warnings.warnings:
            response = widgets.question(_(
                'Your settings have generated some warnings ({} total).  '
                'Check the \'Warnings\' tab for details.'
            ).format(self._preview.warnings.warnings.total), [
                # NOTE: button label in confirmation dialogue
                (_('&Run Anyway'), 'media-playback-start',
                 qt.QMessageBox.AcceptRole),
                qt.QMessageBox.Cancel
            ], default=1, warning=True, ask_again=('run with warnings', 0))

            if response == 1:
                do_run = False

        if do_run:
            self._preview.pause()
            self._gather_finished_emitted = False
            self._thread = RenameThread(self._inputs)
            self.current_operation = None
            self.failed = []
            self._thread.finished.connect(lambda: self._end(True))
            self._thread.signals.start_op.connect(self.start_op)
            self._thread.signals.end_op.connect(self.end_op)
            self._thread.start()
            self.update_status()

        else:
            self._end(False)


    def run (self):
        """Perform the rename operation."""
        if self.state == RunState.idle:
            self.state = RunState.preparing
            self._run_btn.setEnabled(False)
            self.started.emit()
            self.update_status()
            # wait for preview to finish so we can check for warnings
            self._preview.wait(self._continue_run)
