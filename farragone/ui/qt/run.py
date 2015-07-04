# coding=utf-8
"""Farragone Qt UI job running.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from html import escape

from ... import core, util
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
        inps, field_sets, template, options = self._inputs.gather()
        fields = core.field.FieldCombination(*field_sets)
        start_op = self.signals.start_op
        end_op = self.signals.end_op

        renames, done = core.rename.get_renames(
            inps, fields, template, options.cwd)
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
        done()

        self.signals.loaded.emit()


class Run (qt.QVBoxLayout):
    """Button to do the rename, and display current status.

inputs: inp.Input
preview: preview.Preview

Attributes;

started: signal emitted when we start renaming
stopped: signal emitted when we stop renaming; argument indicates whether
         renaming actually started
status: QLabel with current status
running: RenameThread or None
current_operation: (frm, to) paths for the current rename, or None
failed: list of error strings for the current/previous run

"""

    started = qt.pyqtSignal()
    stopped = qt.pyqtSignal(bool)

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
        self._preparing_btns = (
            widgets.mk_button(qt.QPushButton, {
                # NOTE: & marks the keyboard accelerator
                'text': _('&Skip'),
                'icon': 'media-skip-forward',
                'clicked': self._continue_run
            }),
            widgets.mk_button(qt.QPushButton, {
                # NOTE: & marks the keyboard accelerator
                'text': _('&Cancel'),
                'icon': 'process-stop',
                'clicked': self._cancel_run
            })
        )
        for b in self._preparing_btns:
            status_line.addWidget(b)

        self._inputs = inputs
        self._preview = preview
        # not thread-safe, but we only modify it in the main thread
        # True while waiting for preview, RenameThread while running
        self.running = None
        self._can_continue_run = False
        self._has_run = False
        self.current_operation = None
        self.failed = []
        self.update_status()

    def _failed_status (self, as_prefix):
        if as_prefix:
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

    def status_text (self):
        """Get Qt rich text giving the current status."""
        if self.failed:
            if self.running:
                if self.current_operation is not None:
                    text = '{} {}'.format(self._failed_status(as_prefix=True),
                                          self._op_status())
                else:
                    text = self._failed_status(as_prefix=True)
            else:
                text = self._failed_status(as_prefix=False)
        elif self.running:
            if self.current_operation is not None:
                text = self._op_status()
            else:
                text = _('processing...')
        else:
            text = _('success')

        # NOTE: status line
        msg = (_('Running: {}') if self.running
               # NOTE: status line
               else _('Finished: {}'))
        return '<i>{}</i>'.format(msg.format(text))

    def update_status (self):
        """Update display with the current status."""
        preparing = self.running is True
        if preparing:
            self.status.setText('<i>{}</i>'.format(
                # NOTE: status line
                _('checking for problems...')))
        elif self.running or self._has_run:
            self.status.setText(self.status_text())
        else:
            # NOTE: status line
            self.status.setText('<i>{}</i>'.format(_('idle')))

        for b in self._preparing_btns:
            b.show() if preparing else b.hide()

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

    def _end (self, started):
        """Clean up after running.

started: whether renaming actually started (a rename could have been performed)

"""
        if self.running:
            self.running = None
            self._can_continue_run = False
            self.update_status()
            self._preview.resume()
            self.stopped.emit(started)
            self._run_btn.setEnabled(True)

    def _cancel_run (self):
        """Cancel run while waiting for a preview."""
        if self._can_continue_run:
            self._end(False)

    def _continue_run (self):
        """Continuation of `run` - called once a preview is ready."""
        if not self._can_continue_run:
            return
        self._can_continue_run = False
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
            self.running = RenameThread(self._inputs)
            self.current_operation = None
            self.failed = []
            self.running.signals.loaded.connect(lambda: self._end(True))
            self.running.signals.start_op.connect(self.start_op)
            self.running.signals.end_op.connect(self.end_op)

            qt.QThreadPool.globalInstance().start(self.running)
            self._has_run = True
            self.update_status()

        else:
            self._end(False)


    def run (self):
        """Perform the rename operation."""
        if not self.running:
            self.running = True
            self._can_continue_run = True
            self._run_btn.setEnabled(False)
            self.started.emit()
            self.update_status()
            # wait for preview to finish so we can check for warnings
            self._preview.wait(self._continue_run)
