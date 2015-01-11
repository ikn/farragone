IDENT := farragone
INSTALL_PROGRAM := install
INSTALL_DATA := install -m 644

prefix := /usr/local
datarootdir := $(prefix)/share
exec_prefix := $(prefix)
datadir := $(datarootdir)/$(IDENT)
bindir := $(exec_prefix)/bin
docdir := $(datarootdir)/doc/$(IDENT)
python_lib := $(shell ./get_python_lib "$(DESTDIR)$(prefix)")

ICONS := $(wildcard icons/hicolor/*/apps/$(IDENT).png)
ICON_PATTERN := icons/hicolor/%/apps/$(IDENT).png
ICON_PATH = $(patsubst install-%.png,$(ICON_PATTERN),$@)
ICON_PATH_UNINSTALL = $(patsubst uninstall-%.png,$(ICON_PATTERN),$@)

.PHONY: all clean distclean install uninstall

all:
	./setup build

clean:
	$(RM) -r build

distclean: clean
	@ ./configure reverse
	find farragone -type d -name '__pycache__' | xargs $(RM) -r

install-%.png:
	mkdir -p $(shell dirname "$(DESTDIR)$(datarootdir)/$(ICON_PATH)")
	$(INSTALL_DATA) $(ICON_PATH) $(DESTDIR)$(datarootdir)/$(ICON_PATH)

uninstall-%.png:
	$(RM) $(DESTDIR)$(datarootdir)/$(ICON_PATH_UNINSTALL)

install: $(patsubst $(ICON_PATTERN),install-%.png,$(ICONS))
	@ # executable
	./set_prefix "$(prefix)"
	mkdir -p "$(DESTDIR)$(bindir)"
	$(INSTALL_PROGRAM) .run.tmp "$(DESTDIR)$(bindir)/$(IDENT)"
	$(RM) .run.tmp
	@ # package
	./setup install --prefix="$(DESTDIR)$(prefix)"
	@ # readme
	mkdir -p "$(DESTDIR)$(docdir)/"
	@ # readme
	$(INSTALL_DATA) README "$(DESTDIR)$(docdir)/"
	@ # desktop file
	mkdir -p "$(DESTDIR)$(datarootdir)/applications"
	$(INSTALL_DATA) $(IDENT).desktop "$(DESTDIR)$(datarootdir)/applications"

uninstall: $(patsubst $(ICON_PATTERN),uninstall-%.png,$(ICONS))
	@ # executable
	$(RM) "$(DESTDIR)$(bindir)/$(IDENT)"
	$(RM) -r "$(DESTDIR)$(datadir)"
	@ # package
	- ./setup remove --prefix="$(DESTDIR)$(prefix)" &> /dev/null || \
	    $(RM) -r $(python_lib)/{$(IDENT),$(IDENT)-*.egg-info}
	@ # readme
	$(RM) -r "$(DESTDIR)$(docdir)/"
	@ # desktop file
	$(RM) "$(DESTDIR)$(datarootdir)/applications/$(IDENT).desktop"
