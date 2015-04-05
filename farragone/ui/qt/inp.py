"""Farragone Qt UI job configuration.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version."""

import string
import re
import locale
from html import escape

from ... import util, conf, core
from . import doc, qt, widgets


class Dynamic:
    """Has a 'new_widget' signal for when a widget is added.

For widgets added outside the initialisation call, anywhere within this widget
or layout.

"""
    new_widget = qt.pyqtSignal()


class Changing:
    """Has a 'changed' signal for when user input changes."""
    changed = qt.pyqtSignal()


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
    get_state: optional function called with `data` returned by `create` which
               returns a representation of the item's current state
add_tooltip: tooltip for the button to add an item
rm_tooltip: tooltip for the button to remove an item

Emits `new_widget` signal on additions.

Attributes:

types: {type['id']: type} from `types` argument
items: sequence of current items, each a dict with keys:
    type: type['id']
    item: from `create`
    data: from `create`
    state: from `get_state`

"""

    def __init__ (self, types, add_tooltip, rm_tooltip):
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

    def add (self, item_type):
        """Add an item of the given type (`id`)."""
        if item_type not in self.types:
            raise ValueError(item_type)
        item = None

        rm_btn = widgets.mk_button(qt.QPushButton, {
            'icon': 'list-remove',
            'tooltip': self._rm_tooltip,
            'clicked': lambda: self.rm(item)
        })

        def changed ():
            get_state = self.types[item_type].get('getstate')
            item['state'] = (None if get_state is None
                             else get_state(item['data']))
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
            'header': header,
            'item': widget
        }

        self.items.append(item)
        changed()
        self.new_widget.emit()


    def rm (self, item):
        """Remove the given item (QWidget)."""
        self.items.remove(item)
        self.removeWidget(item['item'])
        item['item'].deleteLater()
        self.changed.emit()


class FilesSection (CustomList):
    """UI section for selecting input paths.

Item states are dicts with 'input' being a `core.inputs.Input`.

"""

    # NOTE: UI section heading
    name = _('Files')
    doc = doc.files_section

    def __init__ (self):
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

    def _get_list_state (self, data):
        paths = filter(lambda path: path,
                       data['text_widget'].toPlainText().splitlines())
        return {'input': core.inputs.StaticInput(*paths)}

    def _new_list (self, changed):
        text = qt.QPlainTextEdit()
        text.setLineWrapMode(qt.QPlainTextEdit.NoWrap)
        # QPlainTextEdit.setPlaceholderText is new in Qt 5.3
        try:
            text.setPlaceholderText(_('List of files, one per line'))
        except AttributeError:
            pass
        text.textChanged.connect(changed)
        return {'data': {'text_widget': text}, 'item': text}

    def _get_glob_state (self, data):
        return {'input': core.inputs.GlobInput(data['text_widget'].text())}

    def _new_glob (self, changed):
        text = qt.QLineEdit()
        text.setPlaceholderText(_('Glob-style pattern'))
        # NOTE: default value for the 'Pattern' file source; 'ext' means file
        # extension
        text.setText(_('*.ext'))
        text.textChanged.connect(changed)
        return {'data': {'text_widget': text}, 'item': text}

    def _get_recursive_state (self, data):
        path = data['text_widget'].text()
        return {'input': core.inputs.RecursiveFilesInput(path)}

    def _new_recursive (self, changed):
        text = qt.QLineEdit()
        text.setPlaceholderText(_('Directory path'))
        text.textChanged.connect(changed)
        return {'data': {'text_widget': text}, 'item': text}


class FieldsSection (CustomList):
    """UI section for defining fields.

Item states are dicts with 'fields' being a `core.field.Fields`.

"""

    # NOTE: UI section heading
    name = _('Fields')
    doc = doc.fields_section

    def __init__ (self):
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

    def names (self):
        """Get a set of the names of all defined fields."""
        return set(sum((item['state']['fields'].names
                        for item in self.items), []))

    def _get_component_state (self, data):
        field_name = data['field_widget'].text()
        idx = data['index_widget'].text()
        return {'fields': core.field.PathComponent(field_name, idx)}

    def _new_component (self, changed):
        layout = qt.QHBoxLayout()

        idx = qt.QLineEdit()
        layout.addWidget(idx)
        idx.setText('-1')
        idx.setPlaceholderText(_('Path component index'))
        idx.textChanged.connect(changed)
        field = qt.QLineEdit()
        layout.addWidget(field)
        # NOTE: default value for the field name for the 'Path Component' field
        # source
        field.setText(_('name'))
        field.setPlaceholderText(_('Field name'))
        field.textChanged.connect(changed)

        return {'data': {
            'index_widget': idx,
            'field_widget': field
        }, 'item': layout, 'focus': idx}

    def _get_regex_state (self, data):
        return {'fields': core.field.RegexGroups(
            data['text_widget'].text(), data['field_widget'].text()
        )}

    def _new_regex (self, changed):
        layout = qt.QHBoxLayout()

        text = qt.QLineEdit()
        layout.addWidget(text, 3) # 3 times the size of the field name entry
        # NOTE: default value for the 'Regular Expression' field source; 'ext'
        # means file extension
        text.setText(_('(?P<name>.*)\.(?P<ext>[^.]*)'))
        text.textChanged.connect(changed)
        field = qt.QLineEdit()
        layout.addWidget(field, 1)
        # NOTE: default value for the field name for the 'Path Component' field
        # source
        field.setText(_('group'))
        field.setPlaceholderText(_('Field name'))
        field.textChanged.connect(changed)

        return {'data': {
            'text_widget': text,
            'field_widget': field
        }, 'item': layout, 'focus': text}

    def _get_ordering_state (self, data):
        field_name = data['field_widget'].text()
        key = (
            (lambda s: locale.strxfrm(s.lower()))
            if data['casesensitive_widget'].isChecked()
            else locale.strxfrm
        )
        reverse = not data['ascending_widget'].isChecked()
        return {'fields': core.field.Ordering(field_name, key, reverse)}

    def _new_ordering (self, changed):
        layout = qt.QGridLayout()

        case_sensitive = qt.QCheckBox(_('Case-sensitive'))
        layout.addWidget(case_sensitive, 0, 0)
        case_sensitive.stateChanged.connect(changed)
        # NOTE: sort order
        ascending = qt.QCheckBox(_('Ascending'))
        layout.addWidget(ascending, 0, 1)
        ascending.setChecked(True)
        ascending.stateChanged.connect(changed)

        field = qt.QLineEdit()
        layout.addWidget(field, 1, 0, 1, 2)
        # NOTE: default value for the field name for the 'Ordering' field source
        field.setText(_('position'))
        field.setPlaceholderText(_('Field name'))
        field.textChanged.connect(changed)

        return {'data': {
            'field_widget': field,
            'casesensitive_widget': case_sensitive,
            'ascending_widget': ascending
        }, 'item': layout, 'focus': field}


'''
class FieldTransformsSection (Dynamic, Changing, qt.QVBoxLayout):
    """UI section for defining field transformations."""

    # NOTE: UI section heading
    name = _('Field Transforms')

    def __init__ (self, fields):
        Changing.__init__(self)
        qt.QVBoxLayout.__init__(self)
        self._items = {}
        self._fields = fields
        fields.changed.connect(self._fields_changed)

    def _fields_changed (self):
        current = self._fields.names()
        previous = set(self._items.keys())
        new = current - previous
        for name in new:
            self.add(name)
        for name in previous - current:
            self.rm(name)
        self.changed.emit()
        if new:
            self.new_widget.emit()

    def add (self, name):
        """Add a field transformation with the given name."""
        layout = qt.QHBoxLayout()
        layout.addWidget(widgets.mk_label(name))
        text = qt.QLineEdit()
        layout.addWidget(text)
        text.setPlaceholderText(_('Python 3 code transform'))
        text.textChanged.connect(self.changed)

        row = widgets.widget_from_layout(layout)
        self.addWidget(row)
        self._items[name] = row

    def rm (self, name):
        """Remove a field transformation with the given name."""
        row = self._items.pop(name)
        self.removeWidget(row)
        row.deleteLater()
'''


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
        text.setPlaceholderText(_('Destination path template'))
        text.textChanged.connect(changed_text)
        changed_text('')


class Input (qt.QScrollArea):
    """Section of the UI with controls for defining the renaming scheme.

Attributes:

files: FilesSection
fields: FieldsSection
transforms: FieldTransformsSection
template: TemplateSection

"""

    def __init__ (self, new_widget, changed):
        qt.QScrollArea.__init__(self)
        self.setHorizontalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.setFrameShape(qt.QFrame.NoFrame)

        self.files = FilesSection()
        self.files.new_widget.connect(new_widget)
        self.files.changed.connect(changed)
        self.fields = FieldsSection()
        self.fields.new_widget.connect(new_widget)
        self.fields.changed.connect(changed)
        #self.transforms = FieldTransformsSection(self.fields)
        #self.transforms.new_widget.connect(new_widget)
        #self.transforms.changed.connect(changed)
        self.template = TemplateSection()
        self.template.changed.connect(changed)

        self._layout = qt.QVBoxLayout()
        self.setWidget(widgets.widget_from_layout(self._layout))
        self._layout.setSizeConstraint(qt.QLayout.SetMinAndMaxSize)
        self.add_section(self.files)
        self.add_section(self.fields)
        #self.add_section(self.transforms)
        self.add_section(self.template)

    def add_section (self, section):
        group = qt.QGroupBox(section.name)
        if hasattr(section, 'doc'):
            group.setWhatsThis(section.doc)
        group.setLayout(section)
        self._layout.addWidget(group)

    def gather_fields (self):
        """Return data about fields specified.

Returns `(field_sets, all_fields)`, where:

field_sets: sequence of `core.inputs.Fields`
all_fields: `core.inputs.FieldCombination` containing all fields in `field_sets`

"""
        field_sets = []
        for f in self.fields.items:
            field_sets.append(f['state']['fields'])
        return (field_sets, core.field.FieldCombination(*field_sets))

    def gather (self):
        """Return data defining the renaming scheme.

Returns `(inps, fields, template, transform)`, where:

inps: sequence of `core.inputs.Input`
fields: `core.inputs.Fields`
transform: fields transformation function
template: `string.Template` for the output path

"""
        inps = [f['state']['input'] for f in self.files.items]
        fields = self.gather_fields()[1]
        transform = lambda f: f
        template = self.template.template
        return (inps, fields, transform, template)
