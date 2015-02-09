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
localedir := $(datarootdir)/locale
local_localedir := ./locale

ICON_ROOT := icons/hicolor
ICON_DIRS := $(patsubst $(ICON_ROOT)/%/apps,%,$(wildcard $(ICON_ROOT)/*/apps))
ICON_DIR_PATH = $(ICON_ROOT)/$(patsubst icons-install-%,%,$@)/apps
ICON_DIR_PATH_UNINSTALL = $(ICON_ROOT)/$(patsubst icons-uninstall-%,%,$@)/apps
ICON_PATH_UNINSTALL = $(wildcard $(ICON_DIR_PATH_UNINSTALL)/*)

.PHONY: all inplace clean distclean install uninstall

all:
	./setup build

inplace:
	./i18n/gen_mo "$(local_localedir)"

clean:
	$(RM) -r build
	$(RM) -r "$(local_localedir)"

distclean: clean
	@ ./configure reverse
	find farragone -type d -name '__pycache__' | xargs $(RM) -r

icons-install-%:
	mkdir -p "$(DESTDIR)$(datarootdir)/$(ICON_DIR_PATH)"
	$(INSTALL_DATA) -t "$(DESTDIR)$(datarootdir)/$(ICON_DIR_PATH)" \
	    $(wildcard $(ICON_DIR_PATH)/*)

icons-uninstall-%:
	$(RM) $(patsubst $(ICON_DIR_PATH_UNINSTALL)/%,$(DESTDIR)$(datarootdir)/$(ICON_DIR_PATH_UNINSTALL)/%,$(ICON_PATH_UNINSTALL))

install: $(patsubst %,icons-install-%,$(ICON_DIRS))
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
	@ # locale
	./i18n/gen_mo "$(DESTDIR)$(localedir)"

uninstall: $(patsubst %,icons-uninstall-%,$(ICON_DIRS))
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
	@ # locale
	$(RM) "$(DESTDIR)$(localedir)"/*/LC_MESSAGES/$(IDENT).mo
