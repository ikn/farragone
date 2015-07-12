"""Farragone Qt UI preview system.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from time import time
from html import escape

from ... import core
from ... import conf, util
from . import doc, qt, widgets, sync, outpututil

log = util.logger('qt.output:preview')


class PreviewThread (qt.QObject):
    """For checking and previewing the rename process.

inputs: inp.Inputs
thread: thread `run` is called in

Results are sent in batches because emitting Qt signals very quickly slows down
the UI.

"""

    # qt HTML string to display
    fields = qt.pyqtSignal(str)
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

    def _emit_fields (self, field_sets, all_fields):
        # emit fields signal
        log('BG fields')
        lines = []
        dup_names = all_fields.duplicate_names

        for fields in field_sets:
            source = str(fields)
            for name in fields.names:
                rendered_name = (
                    '<font color="red">{}</font>' if name in dup_names else '{}'
                ).format(escape(name))
                # NOTE: line in the Fields tab; placeholders are the field name
                # and a description of the field's source
                lines.append(_(
                    '{0} <font color="grey">({1})</font>'
                ).format(rendered_name, source))

        self.fields.emit('<br>'.join(lines))

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

        interrupted = False
        # check if we want to abort; return True if so
        def interrupt ():
            nonlocal interrupted
            if interrupted:
                # already aborted
                return True
            else:
                i = self.thread.isInterruptionRequested()
                if i:
                    interrupted = True
                return i

        inps, field_sets, template, options = self._inputs.gather(interrupt)
        fields = core.field.FieldCombination(*field_sets)
        self._emit_fields(field_sets, fields)
        sent = 0
        ops = []
        warnings = list(fields.warnings)

        renames, done = core.warnings.get_renames_with_warnings(
            inps, fields, template, options.cwd, interrupt)
        for (frm, to), new_warnings in renames:
            ops.append((frm, to))
            warnings.extend(new_warnings)
            if self._ready_for_signal():
                self._emit_batch(ops, warnings)
                sent += len(ops)
                ops = []
                warnings = []
            if interrupted or self.thread.isInterruptionRequested():
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


class PreviewRenames (outpututil.Section):
    """Preview for files to be renamed.

Respects conf.MAX_PREVIEW_LENGTH.

Attributes:

num_files: `StatusField` displaying the number of renames processed

"""

    def __init__ (self):
        # NOTE: & marks keyboard accelerator
        page = self._page = qt.QTextEdit()
        outpututil.Section.__init__(self, _('&Preview'), page,
                                    doc=doc.preview_renames)
        page.setReadOnly(True)
        page.setLineWrapMode(qt.QTextEdit.NoWrap)
        self.num_files = outpututil.num_files_field()
        self.add_status_field(self.num_files)

        self.reset()

    def add (self, renames):
        """Show some more renames.

renames: sequence of rename operations, each `(source_path, destination_path)`

"""
        got = len(renames)
        space = conf.MAX_PREVIEW_LENGTH - self._lines
        use = min(space, got)
        if use > 0:
            self._page.insertPlainText(
                '\n'.join(core.rename.preview_rename(frm, to)
                for frm, to in renames[:use]
            ) + '\n')
            self._lines += use
        if got > space and not self._preview_abbreviated:
            self._page.insertPlainText('...\n')
            self._lines += 1
            self._preview_abbreviated = True

    def reset (self):
        """Prepare for a new preview."""
        self._page.setPlainText('')
        self._lines = 0
        self._preview_abbreviated = False
        # status bar
        self.num_files.update(0)


class PreviewWarnings (outpututil.Section):
    """Show warnings for a previewed renaming process.

Attributes:

num_files: `StatusField` displaying the number of renames processed

"""

    def __init__ (self):
        # NOTE: & marks keyboard accelerator
        page = self._page = qt.QTextEdit()
        outpututil.Section.__init__(self, _('&Warnings'), page, icon='dialog-warning',
                             doc=doc.preview_warnings)
        page.setReadOnly(True)
        page.setLineWrapMode(qt.QTextEdit.NoWrap)
        self.num_files = outpututil.num_files_field()
        self.add_status_field(self.num_files)

        self.reset()

    def _update_display (self):
        # update text shown from self.warnings
        self._page.setHtml(self.warnings.render('html'))

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
        self._page.setPlainText('')
        # tab
        self.error = False
        self.new = False
        # status bar
        self.num_files.update(0)


class FieldsSection (outpututil.Section):
    """Displays specified fields and their sources."""

    def __init__ (self):
        page = self._page = qt.QTextEdit()
        # NOTE: & marks keyboard accelerator
        outpututil.Section.__init__(self, _('&Fields'), page, doc=doc.preview_fields)
        page.setReadOnly(True)
        page.setLineWrapMode(qt.QTextEdit.NoWrap)

    def set_text (self, text):
        """Display the given rich text, overriding any existing text."""
        self._page.setHtml(text)
        self.working = False

    def reset (self):
        """Prepare for a new preview."""
        self._page.setPlainText('')


class Preview (sync.UpdateController):
    """Manages preview widgets - renames and warnings.

inputs: inp.Input

Attributes:

renames: PreviewRenames
warnings: PreviewWarnings
fields: FieldsSection

"""

    def __init__ (self, inputs):
        self.renames = PreviewRenames()
        self.warnings = PreviewWarnings()
        self.fields = FieldsSection()

        def run ():
            self._preview.run()

        sync.UpdateController.__init__(self, run, 'preview', log)
        self._preview = PreviewThread(inputs, self.thread)
        self._preview.fields.connect(self._fields_finished)
        self._preview.operation_batch.connect(self._operation_batch_finished)
        self._preview.warning_batch.connect(self._warning_batch_finished)
        self.reset.connect(self._on_reset)
        self.finished.connect(self._on_finished)

        self._num_files = 0

    def _fields_finished (self, fields_text):
        # new fields text
        log('FG fields')
        self.fields.set_text(fields_text)

    def _operation_batch_finished (self, renames):
        # new results
        log('FG ops batch')
        self.renames.add(renames)
        self._num_files += len(renames)
        self.renames.num_files.update(self._num_files)
        self.warnings.num_files.update(self._num_files)

    def _warning_batch_finished (self, batch):
        # new warnings
        log('FG warnings batch')
        self.warnings.add(batch)

    def _on_finished (self):
        """Preview finished or canceled."""
        self.renames.working = False
        self.warnings.working = False

    def _on_reset (self):
        """Prepare for a new preview."""
        self._num_files = 0
        for section in (self.renames, self.warnings, self.fields):
            section.working = True
            section.reset()

    def update (self):
        """Update display from current settings."""
        sync.UpdateController.update(self)
