"""Farragone Qt UI threading/synchronisation utilities.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

from ... import util
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


class UpdateController (qt.QObject):
    """Handle updating the result of a computation in another thread.

reset: function to call before updating, to reset any state
run: function to run in the work thread for each update; should return when
     interrupted (QThread.isInterruptionRequested)
name: worker thread name (display only)
log: logging function (one is created if not given)

Results of the computation can be obtained by emitting signals in `run`.

Attributes:

thread: QThread in which `run` is called
reset, finished: signals for when the thread starts/stops working

"""

    reset = qt.pyqtSignal()
    finished = qt.pyqtSignal()

    def __init__ (self, run, name='worker', log=None):
        qt.QObject.__init__(self)
        self._log = (util.logger('qt.sync.UpdateController')
                     if log is None else log)
        self.thread = _UpdateWorker(run, log)
        self.thread.setObjectName(name)
        self.thread.finished.connect(self._thread_finished)
        self._queued = False
        self._paused = False
        self._finish_cbs = []

    def _start_thread (self):
        # actually reset and start the thread working
        if self._paused:
            self._log('FG start (paused)')
            return False
        else:
            self._log('FG start')
            self.reset.emit()
            self.thread.start()
            return True

    def _thread_finished (self):
        # called when the thread finishes working
        self._log('FG signal finished')

        for cb in self._finish_cbs:
            cb()
        self._finish_cbs = []

        if self._queued:
            # we interrupted the thread - start it again
            self._log('FG starting')
            self._queued = False
            thread = self.thread
            thread.working_lock.lock()
            thread.working = self._start_thread()
            thread.working_lock.unlock()
        else:
            self.finished.emit()

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
            thread.working = self._start_thread()
        thread.working_lock.unlock()

    def pause (self):
        """Stop any current and all future update jobs."""
        self._paused = True
        self.thread.requestInterruption()

    def resume (self):
        """Allow jobs to run after a call to `pause`."""
        self._paused = False

    def wait (self, callback):
        """Wait for an update to finish.

callback: called once, when an update has finished (may have already happened),
          before any subsequent update starts

"""
        do_call = False
        self.thread.working_lock.lock()
        if self.thread.working:
            self._finish_cbs.append(callback)
        else:
            do_call = True
        self.thread.working_lock.unlock()
        # call outside of lock to avoid possible deadlocks
        if do_call:
            callback()


class PauseableThread (qt.QThread):
    """A thread that can be paused and resumed."""

    def __init__ (self):
        qt.QObject.__init__(self)
        self._paused = False
        # whether we've ever waited for an unpause
        self._init = False
        # used to wait for unpause
        self._wait = qt.QWaitCondition()
        # used with the wait condition
        self._lock = qt.QMutex()

    def wait_paused (self):
        if self._paused:
            # QWaitCondition needs the mutex to be locked - we have to do it
            # here for the first time because the constructor doesn't run in
            # this thread
            if not self._init:
                self._lock.lock()
                self._init = True
            # wait for unpause
            self._wait.wait(self._lock)

    @property
    def paused (self):
        """Whether the thread is paused."""
        return self._paused

    @paused.setter
    def paused (self, paused):
        # set this before waking so that threads never wait after waking
        self._paused = paused
        if not paused:
            self._wait.wakeAll()
