import sys
from platform import system
import locale
import os
from os.path import join as join_path

IDENTIFIER = 'farragone'
VERSION = '0.2.2'

PATH_PKG = os.path.dirname(sys.argv[0])
PATH_LOCALE = None
try:
    _local_locale = join_path(PATH_PKG, 'locale')
    if os.path.isdir(_local_locale):
        PATH_LOCALE = _local_locale
except OSError:
    pass
PATH_ICONS = join_path(PATH_PKG, 'icons')

WINDOWS = system() == 'Windows'
FREEDESKTOP = not WINDOWS
if FREEDESKTOP:
    PATH_HOME = os.path.expanduser('~')
    PATH_DATA = (os.environ.get('XDG_DATA_HOME') or
                 join_path(PATH_HOME, '.local', 'share', IDENTIFIER))
    PATH_CONF_WRITE = (os.environ.get('XDG_CONFIG_HOME') or
                       join_path(PATH_HOME, '.config', IDENTIFIER))
    _paths_read = os.environ.get('XDG_CONFIG_DIRS') or '/etc/xdg'
    PATHS_CONF_READ = [
        join_path(path, IDENTIFIER) for path in _paths_read.split(':') if path
    ] + [PATH_CONF_WRITE]

else:
    PATH_HOME = os.environ['USERPROFILE']
    PATH_DATA = join_path(os.environ['APPDATA'], IDENTIFIER)
    PATH_CONF_WRITE = PATH_DATA
    PATHS_CONF_READ = [PATH_CONF_WRITE]
    # set language
    if not os.environ.get('LANG'):
        os.environ['LANG'] = locale.getdefaultlocale()[0]

LOG = {
    'conf.settings': True,
    'qt.widgets.natural_widget_order': False,
    'qt.output:preview': False
}

CONF_FILENAME = 'settings'
# minumum interval between Qt signals for potentially rapid emitters
MIN_SIGNAL_INTERVAL = 0.2
# maximum number of renames shown in the preview
MAX_PREVIEW_LENGTH = 500
# maximum number of warning details to show for each category
MAX_WARNINGS_PER_CATEGORY = 3
# used to find an icon theme
FALLBACK_DESKTOP = 'GNOME'
# for non-freedesktop-aware environments
LOCAL_ICON_THEME = 'Tango'
