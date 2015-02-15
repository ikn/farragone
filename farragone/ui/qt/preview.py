# coding=utf-8
"""Farragone Qt UI preview system.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from time import time
from html import escape

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
    # [(category, detail), ...]
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
        inps, fields, transform, template, warnings = self._inputs.gather()
        interrupted = False
        sent = 0
        ops = []
        warnings = list(warnings)

        for frm, to in core.get_renames(inps, fields, template, transform):
            ops.append((frm, to))
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
        self._lines = 0

    def add (self, renames):
        """Show some more renames.

renames: sequence of rename operations, each `(source_path, destination_path)`

"""
        got = len(renames)
        space = conf.MAX_PREVIEW_LENGTH - self._lines
        use = min(space, got)
        if use > 0:
            self.widget.insertPlainText('\n'.join(
                # NOTE: rename preview: source -> destination
                _('{} → {}').format(repr(frm), repr(to))
                for frm, to in renames[:use]
            ) + '\n')
            self._lines += use
        if got > space:
            self.widget.insertPlainText('...\n')
            self._lines += 1

    def reset (self):
        """Prepare for a new preview."""
        self.widget.setPlainText('')
        self._lines = 0


class PreviewWarnings (widgets.Tab):
    """Show warnings for a previewed renaming process."""

    def __init__ (self):
        # NOTE: & marks keyboard accelerator
        widgets.Tab.__init__(self, _('&Warnings'), qt.QTextEdit(),
                             'dialog-warning')
        self.warnings = {}

    def _update_display (self):
        # update text shown from self.warnings
        lines = []
        for category, warnings in self.warnings.items():
            # NOTE: category line in warnings display; maybe the order should be
            # switched for RTL languages
            lines.append(_('{indent}{text}').format(
                indent='&nbsp;' * 8, text='<b>{}</b>'.format(escape(category))
            ))
            for detail in warnings['details']:
                lines.append(escape(detail))

            extra = warnings['extra']
            if extra:
                # NOTE: for warnings display, where there are extra warnings in
                # a category not displayed; placeholder is how many of these
                # there are
                text = ngettext('(and {} more)', '(and {} more)', extra)
                lines.append('<i>{}</i>'.format(text.format(extra)))

            # gap between each category
            lines.append('')
        self.widget.setHtml('<br>'.join(lines))

    def add (self, warnings):
        """Show some more warnings.

warnings: sequence of warnings, each `(category, detail)` strings

"""
        for category, detail in warnings:
            existing = self.warnings.setdefault(category,
                                                {'details': [], 'extra': 0})
            if (existing['extra'] or
                len(existing['details']) == conf.MAX_WARNINGS_PER_CATEGORY):
                existing['extra'] += 1
            else:
                existing['details'].append(detail)

        if warnings:
            self._update_display()
            self.error = True
            self.new = True

    def reset (self):
        """Prepare for a new preview."""
        self.warnings = {}
        self.widget.setPlainText('')
        self.error = False


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
