"""Farragone Qt UI preview system.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from time import time

from ... import core
from ... import conf, util
from . import qt, widgets, sync

log = util.logger('qt.output:preview')


class PreviewThread (qt.QObject):
    """For checking and previewing the rename process.

inputs: inp.Inputs
thread: thread `run` is called in

Results are sent in batches because emitting Qt signals very quickly slows down
the UI.

"""

    # [(path_from, path_to), ...]
    operation_batch = qt.pyqtSignal(list)
    # [util.Warning, ...]
    warning_batch = qt.pyqtSignal(list)

    def __init__ (self, inputs, thread):
        qt.QObject.__init__(self)
        self._inputs = inputs
        self.thread = thread
        # when we last emitted a signal
        self._last_signal_t = 0

    def _reset_signal (self):
        # reset the signal timer
        self._last_signal_t = time()

    def _emit_batch (self, ops, warnings):
        # emit operation and warning batch signals
        log('BG batch')
        self.operation_batch.emit(ops)
        self.warning_batch.emit(warnings)
        self._reset_signal()

    def _ready_for_signal (self):
        # return whether it's been long enough to emit a signal
        return time() - self._last_signal_t > conf.MIN_SIGNAL_INTERVAL

    def _wait_for_signal (self):
        # sleep until it's been long enough that we can emit a signal
        remain_t = (conf.MIN_SIGNAL_INTERVAL - (time() - self._last_signal_t))
        if remain_t > 0:
            self.thread.usleep(int(1000000 * remain_t))

    def run (self):
        """Validate and generate preview items.

`operation_batch` is emitted with a list of source and destination paths for
each checked rename.

"""
        # reset timer for automatic `started` signal
        self._reset_signal()
        inps, fields, transform, template = self._inputs.gather()
        interrupted = False
        sent = 0
        ops = []

        warnings = list(fields.warnings)
        try:
            template.substitute()
        except ValueError as e:
            warnings.append(util.Warn('template', util.exc_str(e)))
        except KeyError:
            pass

        get, done = core.warnings.get_renames_with_warnings()
        for (frm, to), new_warnings in get(inps, fields, template, transform):
            ops.append((frm, to))
            warnings.extend(new_warnings)
            if self._ready_for_signal():
                self._emit_batch(ops, warnings)
                sent += len(ops)
                ops = []
                warnings = []
            if self.thread.isInterruptionRequested():
                # this preview is no longer needed
                log('BG interrupt')
                interrupted = True
                break
        done()

        # emit unfinished batch
        if not interrupted:
            self._wait_for_signal()
            self._emit_batch(ops, warnings)

        # reset timer for automatic `finished` signal
        self._wait_for_signal()
        self._reset_signal()


class PreviewRenames (widgets.Tab):
    """Preview for files to be renamed.

Respects conf.MAX_PREVIEW_LENGTH.

"""

    def __init__ (self):
        # NOTE: & marks keyboard accelerator
        widgets.Tab.__init__(self, _('&Preview'), qt.QTextEdit())
        self.widget.setReadOnly(True)
        self.widget.setLineWrapMode(qt.QTextEdit.NoWrap)
        self.reset()

    def add (self, renames):
        """Show some more renames.

renames: sequence of rename operations, each `(source_path, destination_path)`

"""
        got = len(renames)
        space = conf.MAX_PREVIEW_LENGTH - self._lines
        use = min(space, got)
        if use > 0:
            self.widget.insertPlainText(
                '\n'.join(core.rename.preview_rename(frm, to)
                for frm, to in renames[:use]
            ) + '\n')
            self._lines += use
        if got > space and not self._preview_abbreviated:
            self.widget.insertPlainText('...\n')
            self._lines += 1
            self._preview_abbreviated = True

    def reset (self):
        """Prepare for a new preview."""
        self.widget.setPlainText('')
        self._lines = 0
        self._preview_abbreviated = False


class PreviewWarnings (widgets.Tab):
    """Show warnings for a previewed renaming process."""

    def __init__ (self):
        # NOTE: & marks keyboard accelerator
        widgets.Tab.__init__(self, _('&Warnings'), qt.QTextEdit(),
                             'dialog-warning')
        self.widget.setReadOnly(True)
        self.widget.setLineWrapMode(qt.QTextEdit.NoWrap)
        self.reset()

    def _update_display (self):
        # update text shown from self.warnings
        self.widget.setHtml(self.warnings.render('html'))

    def add (self, warnings):
        """Show some more warnings.

warnings: sequence of warnings, each `(category, detail)` strings

"""
        for warning in warnings:
            self.warnings.add(warning)
        if warnings:
            self._update_display()
            self.error = True
            self.new = True

    def reset (self):
        """Prepare for a new preview."""
        self.warnings = util.Warnings()
        self.widget.setPlainText('')
        self.error = False
        self.new = False


class Preview (sync.UpdateController):
    """Manages preview widgets - renames and warnings.

inputs: inp.Input

Attributes:

renames: PreviewRenames
warnings: PreviewWarnings

"""

    def __init__ (self, inputs):
        self.renames = PreviewRenames()
        self.warnings = PreviewWarnings()

        def run ():
            self._preview.run()

        sync.UpdateController.__init__(self, self._reset, run, 'preview', log)
        self._preview = PreviewThread(inputs, self.thread)
        self._preview.operation_batch.connect(self._operation_batch_finished)
        self._preview.warning_batch.connect(self._warning_batch_finished)

    def _operation_batch_finished (self, batch):
        # new results
        log('FG ops batch')
        self.renames.add(batch)

    def _warning_batch_finished (self, batch):
        # new warnings
        log('FG warnings batch')
        self.warnings.add(batch)

    def _reset (self):
        """Prepare for a new preview."""
        self.renames.reset()
        self.warnings.reset()
