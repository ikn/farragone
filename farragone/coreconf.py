import sys
from platform import system
import locale
import os
from os.path import join as join_path

IDENTIFIER = 'farragone'
VERSION = '0.1.2'

if system() == 'Windows':
    PATH_HOME = os.environ['USERPROFILE']
    PATH_SHARE = join_path(os.environ['APPDATA'], IDENTIFIER)
    PATH_CONF = PATH_SHARE
    # set language
    if not os.environ.get('LANG'):
        os.environ['LANG'] = locale.getdefaultlocale()[0]
else:
    PATH_HOME = os.path.expanduser('~')
    PATH_SHARE = join_path(PATH_HOME, '.local', 'share', IDENTIFIER)
    PATH_CONF = join_path(PATH_HOME, '.config', IDENTIFIER)
CONF_FILE = join_path(PATH_CONF, 'settings')
PATH_PKG = os.path.dirname(sys.argv[0])
PATH_LOCALE = None
try:
    _local_locale = join_path(PATH_PKG, 'locale')
    if os.path.isdir(_local_locale):
        PATH_LOCALE = _local_locale
except OSError:
    pass
PATH_ICONS = join_path(PATH_PKG, 'icons')

LOG = {
    'qt.widgets.natural_widget_order': False,
    'qt.output:preview': False
}
