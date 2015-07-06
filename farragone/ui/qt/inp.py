"""Farragone Qt UI job configuration.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import string
import re
import os
import locale
from html import escape

from ... import util, conf, core
from ...core.field import Alignments, SortTypes
from . import doc, qt, widgets


def optimise_paths (cwd, paths):
    """Make paths relative if it makes them simpler.

cwd: directory relative paths are relative to
paths: iterable of paths

"""
    for path in paths:
        rel = os.path.relpath(path, cwd)
        # we call a path simpler if it has at least 2 fewer path components
        # this is just a rough count, no need to be accurate (would involve
        # os.path.split in a loop)
        yield rel if path.count(os.sep) - rel.count(os.sep) >= 2 else path


class Dynamic:
    """Has a 'new_widget' signal for when a widget is added.

For widgets added outside the initialisation call, anywhere within this widget
or layout.

"""
    new_widget = qt.pyqtSignal()


class Changing:
    """Has a 'changed' signal for when user input changes."""
    changed = qt.pyqtSignal()


class FieldContext (qt.QComboBox):
    """A combo box widget providing a choice of field `Context`."""

    def __init__ (self):
        qt.QComboBox.__init__(self)
        self.setToolTip(_('The part of the path to work with'))

        widgets.add_combobox_items(self, *(
            {
                qt.Qt.UserRole: context,
                qt.Qt.DisplayRole: context.name,
                qt.Qt.ToolTipRole: context.desc
            } for context in core.field.all_contexts
        ))

    @property
    def context (self):
        """Get the currently selected `Context`."""
        return self.currentData()


class OrderingPadding (Dynamic, qt.QGridLayout):
    """Layout containing widgets for 'ordering' field padding settings.

files: `FilesSection`
changed: function to call when any settings change

"""

    # icon names by `Alignment` instance
    ALIGNMENT_ICONS = {
        Alignments.right: 'format-justify-right',
        Alignments.centre: 'format-justify-center',
        Alignments.left: 'format-justify-left'
    }

    def __init__ (self, files, changed):
        Dynamic.__init__(self)
        qt.QGridLayout.__init__(self)
        self._files = files
        self._options = []
        self._enabled = enabled = qt.QCheckBox(_('Padding'))
        self.addWidget(enabled, 0, 0, 1, 3)
        enabled.setToolTip(_('Add padding around the number within the field'))
        enabled.stateChanged.connect(lambda: self._toggle(changed))

        self._char = char = qt.QLineEdit()
        self._options.append(char)
        widgets.set_text_desc(char, _('Padding character'))
        char.setMaxLength(1)
        char.setText('0')
        char.textChanged.connect(changed)

        self._align = align = qt.QComboBox()
        self._options.append(align)
        align.setToolTip(_('Alignment of the number within the field value'))
        widgets.add_combobox_items(align, *(
            {
                'icon': self.ALIGNMENT_ICONS[alignment],
                qt.Qt.UserRole: alignment,
                qt.Qt.DisplayRole: alignment.name
            } for alignment in core.field.all_alignments
        ))
        align.currentIndexChanged.connect(changed)

        self._size = size = qt.QSpinBox()
        self._options.append(size)
        size.setRange(0, 99)
        size.setValue(0)
        size.setToolTip(_('Minimum padded size'))
        size.valueChanged.connect(changed)
        # maps to min value (0, which is also the default)
        size.setSpecialValueText(_('Auto'))

        for i, w in enumerate(self._options):
            self.addWidget(w, 1, i)
        self._toggle(lambda: None)

    def _is_enabled (self):
        return self._enabled.isChecked()

    # called when padding is enabled or disabled
    def _toggle (self, changed):
        enabled = self._is_enabled()
        for w in self._options:
            w.setVisible(enabled)
        changed()
        self.new_widget.emit()

    def get_fmt (self, interrupt=None):
        """Get a formatting function for the current settings.

interrupt: abort when this function returns True

For use as the `fmt` argument to `Ordering`.

"""
        if self._is_enabled():
            size = self._size.value()
            if size == 0: # auto
                size = core.field.Ordering.auto_padding_size(
                    self._files.inputs, interrupt)
            return core.field.Ordering.padding_fmt(
                self._char.text() or ' ', self._align.currentData(), size)
        else:
            return str


class CustomList (Dynamic, Changing, qt.QVBoxLayout):
    """User-modifiable list of items, arranged vertically.

types: sequence of definitions of types of items, where the order is preserved
       when presented, with the first the default; each is a dict with keys:
    id: unique identifier
    name: displayed name
    description: short description
    create: function called like
        `create(changed) -> {'data': data, 'item': item[, 'focus': focus] }` to
        create an item of this type
            changed: function to call with no arguments when any of the form
                     fields in the item change
            data: passed to `get_state`
            item: the created item (QWidget or QLayout)
            focus: widget to focus when added (default: `item`)
    getstate: optional function called with `data` returned by `create`, and a
              function `interrupt`; returns a representation of the item's
              current state
add_tooltip: tooltip for the button to add an item
rm_tooltip: tooltip for the button to remove an item

Emits `new_widget` signal on additions.

Attributes:

types: {type['id']: type} from `types` argument
items: sequence of current items, each a dict with keys:
    type: type['id']
    data: from `create`
    item: from `create`
    changed: called whenever the item's settings change to update `state`
    getstate: item_type's `getstate`
    state: from `getstate`, None if no `getstate` (possibly missing, use
           `CustomList.item_state`)
    queued: True if the item's state has changed but this is not yet reflected
            in `state`

"""

    # runs getstate for all items
    _refresh = qt.pyqtSignal()

    def __init__ (self, types, add_tooltip, rm_tooltip):
        Dynamic.__init__(self)
        Changing.__init__(self)
        qt.QVBoxLayout.__init__(self)

        new_type = qt.QComboBox()
        self.addWidget(new_type)
        # https://bugreports.qt.io/browse/QTBUG-40807
        add_type = lambda i: self.add(new_type.itemData(i))
        new_type.activated.connect(util.rate_limit(0.1, add_type))

        widgets.add_combobox_items(new_type, *(
            {
                'icon': 'list-add',
                qt.Qt.UserRole: data['id'],
                qt.Qt.DisplayRole: data['name'],
                qt.Qt.ToolTipRole: data['description']
            } for data in types
        ))

        self.types = {data['id']: data for data in types}
        self._rm_tooltip = rm_tooltip
        self.items = []

    @staticmethod
    def item_state (item, interrupt=None):
        """Get the state of an item, using its type's `getstate` function.

interrupt: abort when this function returns True

May block for a long time, so shouldn't be called in the UI thread.

"""
        if item['queued']:
            get_state = item['getstate']
            item['state'] = (None if get_state is None
                             else get_state(item['data'], interrupt))
        return item['state']

    def add (self, item_type):
        """Add an item of the given type (`id`).

Returns the item, as added to `CustomList.items`.

"""
        if item_type not in self.types:
            raise ValueError(item_type)
        item = None

        rm_btn = widgets.mk_button(qt.QPushButton, {
            'icon': 'list-remove',
            'tooltip': self._rm_tooltip,
            'clicked': lambda: self.rm(item)
        })

        def changed ():
            item['queued'] = True
            self.changed.emit()

        defn = self.types[item_type]
        header = widgets.mk_label('<b>{}</b>'.format(escape(defn['name'])),
                                  rich=True, tooltip=defn['description'])
        header.setContentsMargins(5, 5, 5, 5)
        result = defn['create'](changed)
        controls = result['item']

        layout = qt.QGridLayout()
        layout.setColumnStretch(0, 1)
        layout.addWidget(header, 0, 0)
        (layout.addLayout if isinstance(controls, qt.QLayout)
         else layout.addWidget)(controls, 1, 0, 1, 2, qt.Qt.AlignTop)
        layout.addWidget(rm_btn, 0, 1)
        widget = widgets.widget_from_layout(layout)
        if 'doc' in defn:
            widget.setWhatsThis(defn['doc'])
        self.insertWidget(len(self.items), widget)

        # focus specific widget, or the main one, or any we can find
        focus = result.get('focus')
        if isinstance(focus, qt.QWidget):
            pass
        elif isinstance(controls, qt.QWidget):
            focus = controls
        else:
            focus = widgets.first_layout_widget(controls)
        if focus is not None:
            focus.setFocus(qt.Qt.OtherFocusReason)
            # for text boxes, also select all text
            if isinstance(focus,
                          (qt.QLineEdit, qt.QTextEdit, qt.QPlainTextEdit)):
                focus.selectAll()

        item = {
            'type': item_type,
            'data': result['data'],
            'item': widget,
            'changed': changed,
            'getstate': self.types[item_type].get('getstate'),
            'queued': False
        }

        self.items.append(item)
        self._refresh.connect(changed)
        changed()
        self.new_widget.emit()
        return item


    def rm (self, item):
        """Remove the given item (from `CustomList.items`)."""
        self.items.remove(item)
        self.removeWidget(item['item'])
        item['item'].deleteLater()
        self._refresh.disconnect(item['changed'])
        self.changed.emit()
        self.new_widget.emit()


    def refresh (self):
        """Run the `getstate` function for all items."""
        self._refresh.emit()


class FilesSection (CustomList):
    """UI section for selecting input paths.

options: OptionsSection

Item states are dicts with 'input' being a `core.inputs.Input`.

"""

    # NOTE: UI section heading
    name = _('Files')
    doc = doc.files_section

    def __init__ (self, options):
        CustomList.__init__(self, [
            {
                'id': 'glob',
                # NOTE: file source type name
                'name': _('Pattern'),
                'description': _('Use a glob-style pattern'),
                'create': self._new_glob,
                'getstate': self._get_glob_state,
                'doc': doc.files_glob
            }, {
                'id': 'list',
                # NOTE: file source type name
                'name': _('List'),
                'description': _('Specify files manually'),
                'create': self._new_list,
                'getstate': self._get_list_state,
                'doc': doc.files_list
            }, {
                'id': 'recursive',
                # NOTE: file source type name
                'name': _('Recursive Files'),
                'description': _(
                    'Specify a directory in which to find files recursively'
                ),
                'create': self._new_recursive,
                'getstate': self._get_recursive_state,
                'doc': doc.files_recursive
            }
        ], _('Add a source of files'), _('Remove this source of files'))

        self._options = options
        options.changed.connect(self.refresh)
        # if None, should use cwd
        self._last_file_browser_dir_value = None

    @property
    def inputs (self):
        """Sequence of `inputs.Input`."""
        return [CustomList.item_state(f)['input'] for f in self.items]

    @property
    def _last_file_browser_dir (self):
        return (self._options.cwd if self._last_file_browser_dir_value is None
                else self._last_file_browser_dir_value)

    @_last_file_browser_dir.setter
    def _last_file_browser_dir (self, d):
        self._last_file_browser_dir_value = d

    # add paths with a new list item
    def add_paths (self, paths):
        if paths:
            item = self.add('list')
            item['data']['add_paths'](
                optimise_paths(self._last_file_browser_dir, paths))

    def _get_list_state (self, data, interrupt):
        paths = filter(lambda path: path,
                       data['text_widget'].toPlainText().splitlines())
        return {'input': core.inputs.StaticInput(*paths)}

    # show a file dialogue and pass files to the given function
    def _list_browse (self, add_paths):
        # can't use a static function since we need the current dir afterwards
        fd_dir = self._last_file_browser_dir
        fd = qt.QFileDialog(directory=fd_dir)
        fd.setFileMode(qt.QFileDialog.ExistingFiles)
        fd.setOptions(qt.QFileDialog.HideNameFilterDetails)

        if fd.exec():
            files = fd.selectedFiles()
            add_paths(files)
            self._last_file_browser_dir = fd.directory().absolutePath()

    def _new_list (self, changed):
        layout = qt.QVBoxLayout()

        text = qt.QPlainTextEdit()
        layout.addWidget(text)
        text.setLineWrapMode(qt.QPlainTextEdit.NoWrap)
        widgets.set_text_desc(text, _('List of files, one per line'))
        text.textChanged.connect(changed)

        # append given iterable of paths to the list widget
        def add_paths (paths):
            text.appendPlainText('\n'.join(paths) + '\n')
            text.setFocus(qt.Qt.OtherFocusReason)

        browse = widgets.mk_button(qt.QPushButton, {
            # NOTE: label for a button that opens a file browser dialogue
            'text': _('Browse...'),
            'icon': 'document-open',
            'clicked': lambda: self._list_browse(add_paths)
        })
        layout.addWidget(browse)

        return {
            'data': {'text_widget': text, 'add_paths': add_paths},
            'item': layout
        }

    def _get_glob_state (self, data, interrupt):
        inp = core.inputs.GlobInput(
            data['text_widget'].text(), self._options.cwd)
        return {'input': inp}

    def _new_glob (self, changed):
        text = qt.QLineEdit()
        widgets.set_text_desc(text, _('Glob-style pattern'))
        # NOTE: default value for the 'Pattern' file source; 'ext' means file
        # extension
        text.setText(_('*.ext'))
        text.textChanged.connect(changed)
        return {'data': {'text_widget': text}, 'item': text}

    def _get_recursive_state (self, data, interrupt):
        path = data['text_widget'].text()
        return {
            'input': core.inputs.RecursiveFilesInput(path, self._options.cwd)
        }

    def _new_recursive (self, changed):
        text = qt.QLineEdit()
        widgets.set_text_desc(text, _('Directory path'))
        text.textChanged.connect(changed)
        return {'data': {'text_widget': text}, 'item': text}


class FieldsSection (CustomList):
    """UI section for defining fields.

Item states are dicts with 'fields' being a `core.field.Fields`.

files: `FilesSection`

"""

    # NOTE: UI section heading
    name = _('Fields')
    doc = doc.fields_section

    def __init__ (self, files):
        CustomList.__init__(self, [
            {
                'id': 'component',
                # NOTE: field source type name
                'name': _('Path Component'),
                'description':
                    _('Use the filename or a directory from the path'),
                'create': self._new_component,
                'getstate': self._get_component_state,
                'doc': doc.fields_component
            }, {
                'id': 'regex',
                # NOTE: field source type name
                'name': _('Regular Expression'),
                'description': 'Capture groups from a matching regex',
                'create': self._new_regex,
                'getstate': self._get_regex_state,
                'doc': doc.fields_regex
            }, {
                'id': 'ordering',
                # NOTE: field source type name
                'name': _('Ordering'),
                'description': _('Use the position when the files are ordered'),
                'create': self._new_ordering,
                'getstate': self._get_ordering_state,
                'doc': doc.fields_ordering
            }
        ], _('Add a source of fields'), _('Remove this source of fields'))
        self._files = files
        files.changed.connect(self.refresh)

    def names (self):
        """Get a set of the names of all defined fields."""
        return set(sum((CustomList.item_state(item)['fields'].names
                        for item in self.items), []))

    def _get_component_state (self, data, interrupt):
        return {'fields': core.field.PathComponent(
            field_name=data['field_widget'].text(),
            index=data['index_widget'].text()
        )}

    def _new_component (self, changed):
        layout = qt.QHBoxLayout()

        idx = qt.QLineEdit()
        layout.addWidget(idx)
        idx.setText('-1')
        widgets.set_text_desc(idx, _('Path component index'))
        idx.textChanged.connect(changed)
        field = qt.QLineEdit()
        layout.addWidget(field)
        # NOTE: default value for the field name for the 'Path Component' field
        # source
        field.setText(_('name'))
        widgets.set_text_desc(field, _('Field name'))
        field.textChanged.connect(changed)

        return {'data': {
            'index_widget': idx,
            'field_widget': field
        }, 'item': layout, 'focus': idx}

    def _get_regex_state (self, data, interrupt):
        return {'fields': core.field.RegexGroups(
            pattern=data['text_widget'].text(),
            field_name_prefix=data['field_widget'].text(),
            context=data['context_widget'].context
        )}

    def _new_regex (self, changed):
        layout = qt.QGridLayout()

        text = qt.QLineEdit()
        layout.addWidget(text, 0, 0, 1, 2)
        # NOTE: default value for the 'Regular Expression' field source; 'ext'
        # means file extension
        text.setText(_('(?P<name>.*)\.(?P<ext>[^.]*)'))
        text.textChanged.connect(changed)

        context = FieldContext()
        layout.addWidget(context, 1, 0, 1, 1)
        context.currentIndexChanged.connect(changed)
        field = qt.QLineEdit()
        layout.addWidget(field, 1, 1, 1, 1)
        # NOTE: default value for the field name for the 'Path Component' field
        # source
        field.setText(_('group'))
        widgets.set_text_desc(field, _('Field name'))
        field.textChanged.connect(changed)

        return {'data': {
            'text_widget': text,
            'context_widget': context,
            'field_widget': field
        }, 'item': layout, 'focus': text}

    def _get_ordering_state (self, data, interrupt):
        base_key = data['sorttype_widget'].currentData()
        key = (
            base_key
            if data['casesensitive_widget'].isChecked()
            else lambda s: base_key(s.lower())
        )

        return {'fields': core.field.Ordering(
            field_name=data['field_widget'].text(),
            key=key,
            reverse=not data['ascending_widget'].isChecked(),
            context=data['context_widget'].context,
            fmt=data['pad'].get_fmt(interrupt)
        )}

    def _new_ordering (self, changed):
        layout = qt.QGridLayout()

        sort_type = qt.QComboBox()
        widgets.add_combobox_items(sort_type, *(
            {
                qt.Qt.UserRole: sort_type,
                qt.Qt.DisplayRole: sort_type.name,
                qt.Qt.ToolTipRole: sort_type.desc
            } for sort_type in core.field.all_sort_types
        ))
        sort_type.currentIndexChanged.connect(changed)
        layout.addWidget(sort_type, 0, 0)

        case_sensitive = qt.QCheckBox(_('Case-sensitive'))
        layout.addWidget(case_sensitive, 0, 1)
        case_sensitive.stateChanged.connect(changed)
        # NOTE: sort order
        ascending = qt.QCheckBox(_('Ascending'))
        layout.addWidget(ascending, 0, 2)
        ascending.setChecked(True)
        ascending.stateChanged.connect(changed)

        context = FieldContext()
        layout.addWidget(context, 1, 0, 1, 1)
        context.currentIndexChanged.connect(changed)
        field = qt.QLineEdit()
        layout.addWidget(field, 1, 1, 1, 2)
        # NOTE: default value for the field name for the 'Ordering' field source
        field.setText(_('position'))
        widgets.set_text_desc(field, _('Field name'))
        field.textChanged.connect(changed)

        pad = OrderingPadding(self._files, changed)
        pad.new_widget.connect(self.new_widget.emit)
        layout.addLayout(pad, 2, 0, 1, 2)

        return {'data': {
            'sorttype_widget': sort_type,
            'casesensitive_widget': case_sensitive,
            'ascending_widget': ascending,
            'context_widget': context,
            'field_widget': field,
            'pad': pad
        }, 'item': layout, 'focus': field}


class TemplateSection (Changing, qt.QVBoxLayout):
    """UI section for defining the output path template.

Attributes:

template: `string.Template`

"""

    # NOTE: UI section heading
    name = _('Output Template')
    doc = doc.template

    def __init__ (self):
        Changing.__init__(self)
        qt.QVBoxLayout.__init__(self)

        def changed_text (text):
            self.template = string.Template(text)
            self.changed.emit()

        text = qt.QLineEdit()
        self.addWidget(text)
        widgets.set_text_desc(text, _('Destination path template'))
        text.textChanged.connect(changed_text)
        changed_text('')


class OptionsSection (Changing, qt.QFormLayout):
    """UI section for setting options."""

    # NOTE: UI section heading
    name = _('Options')

    def __init__ (self):
        qt.QFormLayout.__init__(self)

        self._cwd = cwd = widgets.DirButton(os.getcwd())
        self.addRow(_('Working &directory:'), cwd)
        cwd.setWhatsThis(doc.cwd_section)
        cwd.changed.connect(self.changed.emit)

        # NOTE: checkbox label for option to copy files instead of renaming
        self._copy = copy = qt.QCheckBox(_('Copy files'))
        copy.setToolTip(_('Instead of renaming items, copy them (slower)'))
        copy.setChecked(False)
        # NOTE: heading for a set of options
        self.addRow(_('When running:'), copy)

    @property
    def cwd (self):
        """Path for the current working directory to use for relative paths."""
        return self._cwd.path

    @property
    def copy (self):
        """Whether to copy files instead of renaming."""
        return self._copy.isChecked()


class Input (qt.QScrollArea):
    """Section of the UI with controls for defining the renaming scheme.

new_widget: function to call when widgets are added
changed: function to call when any settings change

Attributes:

files: FilesSection
fields: FieldsSection
template: TemplateSection
options: OptionsSection

"""

    def __init__ (self, new_widget, changed):
        qt.QScrollArea.__init__(self)
        self.setHorizontalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.setFrameShape(qt.QFrame.NoFrame)

        self.options = OptionsSection()
        self.options.changed.connect(changed)
        self.files = FilesSection(self.options)
        self.files.new_widget.connect(new_widget)
        self.files.changed.connect(changed)
        self.fields = FieldsSection(self.files)
        self.fields.new_widget.connect(new_widget)
        self.fields.changed.connect(changed)
        self.template = TemplateSection()
        self.template.changed.connect(changed)

        self._layout = qt.QVBoxLayout()
        self.setWidget(widgets.widget_from_layout(self._layout))
        self._layout.setSizeConstraint(qt.QLayout.SetMinAndMaxSize)
        self.add_section(self.files)
        self.add_section(self.fields)
        self.add_section(self.template)
        self.add_section(self.options)

    def add_section (self, section):
        group = qt.QGroupBox(section.name)
        if hasattr(section, 'doc'):
            group.setWhatsThis(section.doc)
        group.setLayout(section)
        self._layout.addWidget(group)

    def gather (self, interrupt=None):
        """Return data defining the renaming scheme.

interrupt: abort when this function returns True

May block for a long time, so shouldn't be called in the UI thread.

Returns `(inps, fields, template, cwd)`, where:

inps: sequence of `core.inputs.Input`
fields: sequence of `core.inputs.Fields`
template: `string.Template` for the output path
options: `OptionsSection`

"""
        field_sets = []
        for f in self.fields.items:
            field_sets.append(CustomList.item_state(f, interrupt)['fields'])

        return (
            self.files.inputs,
            field_sets,
            self.template.template,
            self.options
        )
