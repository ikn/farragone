"""Farragone Qt UI initialisation routines.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import os
import signal
from platform import system
from multiprocessing import Pipe, Process

from ... import conf, util
from . import qt, window

_freedesktop = system() != 'Windows'
# contains desktop environment (if any) on freedesktop systems
_desktop_lookup = 'XDG_CURRENT_DESKTOP'


def get_fallback_icon_theme (local_theme, fallback_desktop):
    """Determine a fallback icon theme for DEs Qt doesn't know about.

local_theme: name of the theme to use when the system doesn't understand
             system/user themes - probably distributed with the application
             (path must be added manually)
fallback_desktop: desktop environment to use to determine the fallback theme in
                  some cases (eg. GNOME to use the user's GTK theme) (from
                  http://standards.freedesktop.org/menu-spec/latest/apb.html)

This must be called before creating the Qt application.

Returns the theme name.

"""

    # create a Qt application in a separate process to determine the fallback
    # theme - comes from DE-specific config files
    def get_fallback_theme (pipe):
        os.environ[_desktop_lookup] = fallback_desktop
        app = qt.QApplication([])
        pipe.send(qt.QIcon.themeName())

    if not _freedesktop:
        fallback_theme = local_theme
    elif os.environ.get(_desktop_lookup):
        fallback_theme = None
    else:
        # must do this before creating an application in the main process
        pipe_out, pipe_in = Pipe(duplex=False)
        p = Process(target=get_fallback_theme, args=(pipe_in,))
        p.start()
        p.join()
        fallback_theme = pipe_out.recv()
    return fallback_theme


def apply_fallback_icon_theme (fallback_theme):
    """Apply a fallback icon theme if necessary.

fallback_theme: theme name (probably from `get_fallback_icon_theme`)

This must be called after creating the Qt application.

"""

    def bad_icon_theme (name):
        # if there's no theme name, no lookups are performed
        # hicolor is missing important icons
        return not name or name == 'hicolor'

    current_theme = qt.QIcon.themeName()
    if bad_icon_theme(current_theme):
        if bad_icon_theme(fallback_theme):
            util.warn(_('no suitable icon theme found'))
        else:
            qt.QIcon.setThemeName(fallback_theme)


def init ():
    """Start the Qt UI.

Returns when the user quits.

"""
    fallback_theme = get_fallback_icon_theme(conf.LOCAL_ICON_THEME,
                                             conf.FALLBACK_DESKTOP)
    app = qt.QApplication([])
    apply_fallback_icon_theme(fallback_theme)

    # add icon theme path for application icon for running in-place
    qt.QIcon.setThemeSearchPaths(qt.QIcon.themeSearchPaths() +
                                 [conf.PATH_ICONS])

    app.setApplicationName(conf.APPLICATION)
    app.setApplicationVersion(conf.VERSION)
    app.setWindowIcon(qt.QIcon.fromTheme(conf.IDENTIFIER))

    # without this, the signal must go through the Python interpreter, but when
    # using Qt the interpreter might not run very often, so nothing will happen
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    w = window.Window()
    w.show()
    app.exec()
