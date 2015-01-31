"""Farragone Qt UI preview system.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from time import time

from ... import core
from .. import conf, util
from . import qt, sync

log = util.logger('qt.output:preview')


class Preview (qt.QObject):
    """For checking and previewing the rename process.

inputs: inp.Inputs
thread: thread `run` is called in

Results are sent in batches because emitting Qt signals very quickly slows down
the UI.

"""

    # [(path_from, path_to), ...]
    operation_batch = qt.pyqtSignal(list)

    def __init__ (self, inputs, thread):
        qt.QObject.__init__(self)
        self._inputs = inputs
        self.thread = thread
        # when we last emitted a signal
        self._last_signal_t = 0

    def _reset_signal (self):
        # reset the signal timer
        self._last_signal_t = time()

    def _emit_batch (self, batch):
        # emit an operation batch signal
        log('BG batch')
        self.operation_batch.emit(batch)
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
        # add 1 so the signal receiver (UI) knows we have more than it wants
        lim = conf.MAX_PREVIEW_LENGTH + 1
        batch = []

        for frm, to in core.get_renames(inps, fields, template, transform):
            batch.append((frm, to))
            if sent + len(batch) == lim:
                # no more to send - we emit the current batch after the loop
                break
            if self._ready_for_signal():
                self._emit_batch(batch)
                sent += len(batch)
                batch = []
            if self.thread.isInterruptionRequested():
                # this preview is no longer needed
                log('BG interrupt')
                interrupted = True
                break

        # emit unfinished batch
        if not interrupted:
            self._wait_for_signal()
            self._emit_batch(batch)

        # reset timer for automatic `finished` signal
        self._wait_for_signal()
        self._reset_signal()


class Output (sync.UpdateController, qt.QTextEdit):
    """Preview for files to be renamed.

inputs: inp.Input

"""

    def __init__ (self, inputs):
        def run ():
            self._preview.run()

        sync.UpdateController.__init__(self, self._reset, run, 'preview', log)
        self._preview = Preview(inputs, self.thread)
        self._preview.operation_batch.connect(self._operation_batch_finished)

        qt.QTextEdit.__init__(self)
        self.setReadOnly(True)
        self.setLineWrapMode(qt.QTextEdit.NoWrap)
        self._lines = 0

    def _operation_batch_finished (self, batch):
        # new results to display
        log('FG batch')
        got = len(batch)
        space = conf.MAX_PREVIEW_LENGTH - self._lines
        use = min(space, got)
        if use > 0:
            self.insertPlainText('\n'.join(
                '{} → {}'.format(repr(frm), repr(to))
                for frm, to in batch[:use]
            ) + '\n')
            self._lines += use
        if got > space:
            self.insertPlainText('...\n')
            self._lines += 1

    def _reset (self):
        # prepare for a new preview
        self.setPlainText('')
        self._lines = 0
