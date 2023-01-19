Farragone 0.2.5-next.

A batch file renamer for programmers.

http://ikn.org.uk/app/farragone

# License

Distributed under the terms of the
[GNU General Public License, version 3](http://www.gnu.org/licenses/gpl-3.0.txt).

# Installation

Build dependencies:
- [Setuptools](https://setuptools.readthedocs.io/en/latest/)
- [Bash](https://www.gnu.org/software/bash/)

There is no installation method on Windows.

Run `make`, `make install`.  The makefile respects the `prefix`, `DESTDIR`, etc.
arguments.  To uninstall, run `make uninstall`.  `make clean` and
`make distclean` are also supported.

# Dependencies

- [Python 3](http://www.python.org) (>= 3.1)
- [xkbcommon-x11](http://xkbcommon.org)
- [PyQt5](http://www.riverbankcomputing.com/software/pyqt) (>= 5.2)
- [Qt](http://qt-project.org) (>= 5.2)

# Usage

On Unix-like OSs, once installed, just run `farragone` (installed to
/usr/local/bin/ by default).  Alternatively, you can run in-place without
installing by running `make inplace`, `./run`.

On Windows, in the source directory, run `python3 run`, where `python3` is the
Python 3 interpreter.

In any case, files may be specified as command-line arguments.

For help on using the application, use the 'What's This?' button located at the
bottom of the main window and then select part of the UI to get documentation
for.  (Alternatively, press shift + F1 while the part of the UI to get
documentation for is focused.)
