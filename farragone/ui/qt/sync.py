"""Farragone Qt UI threading/synchronisation utilities.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from .. import util
from . import qt


class _UpdateWorker (qt.QThread):
    """Worker thread for `UpdateController`.

run: work function
log: logging function

"""
    def __init__ (self, run, log):
        qt.QThread.__init__(self)
        self.working = False
        self.working_lock = qt.QMutex()
        self._run = run
        self._log = log

    def run (self):
        self._log('BG start')
        self._run()
        self._log('BG finishing')
        self.working_lock.lock()
        self.working = False
        self.working_lock.unlock()
        self._log('BG finished')


class UpdateController:
    """Handle updating the result of a computation in another thread.

reset: function to call before updating, to reset any state
run: function to run in the work thread for each update; should return when
     interrupted (QThread.isInterruptionRequested)
name: worker thread name (display only)
log: logging function (one is created if not given)

Results of the computation can be obtained by emitting signals in `run`.

Attributes:

thread: QThread in which `run` is called

"""

    def __init__ (self, reset, run, name='worker', log=None):
        self._reset = reset
        self._log = (util.logger('qt.sync.UpdateController')
                     if log is None else log)
        self.thread = _UpdateWorker(run, log)
        self.thread.setObjectName(name)
        self.thread.finished.connect(self._thread_finished)
        self._queued = False
        self._exited = False

    def _start_thread (self):
        # actually reset and start the thread working
        if not self._exited:
            self._log('FG start')
            self._reset()
            self.thread.start()

    def _thread_finished (self):
        # called when the thread finishes working
        self._log('FG signal finished')
        if self._queued:
            # we interrupted the thread - start it again
            self._log('FG starting')
            self._queued = False
            thread = self.thread
            thread.working_lock.lock()
            thread.working = True
            thread.working_lock.unlock()
            self._start_thread()

    def update (self):
        """Re-run the computation.

Stops any running computation as quickly as possible and starts again.  This may
be called at any time, but only ever in a single thread.

"""
        self._log('FG update')
        thread = self.thread
        thread.working_lock.lock()
        if thread.working:
            # within this lock, thread can't finish
            # interrupt, release lock and queue up a run on the finish signal
            self._log('FG interrupt')
            self._queued = True
            thread.requestInterruption()
        else:
            # if thread is running, it won't take long to finish, so just wait
            self._log('FG wait')
            thread.wait()
            thread.working = True
            self._start_thread()
        thread.working_lock.unlock()

    def quit (self):
        """Stop any current and all future update jobs."""
        self._exited = True
        self.thread.requestInterruption()
