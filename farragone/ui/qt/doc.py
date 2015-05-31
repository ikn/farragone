files_section = _(r'''
<p>Use this section to add files for renaming.  Add a source of files by selecting a type from the dropdown.</p>

<p>When entering file paths or patterns:</p>
<ul>
    <li><i>~</i> at the start of the path is interpreted as the current user's home directory (eg. <i>/home/user</i> or <i>C:\Users\user</i>).</li>
    <li>Relative paths are relative to the directory the program was started in.</li>
    <li>Escapes (eg. <i>\t</i> or <i>\n</i>) are not supported and will be interpreted literally.</li>
</ul>
''')

files_glob = _(r'''
<p>Enter a Unix-shell-style glob pattern to include all matching files.  See <a href="http://linux.die.net/man/7/glob">the glob man page</a> for details.</p>

<p>Examples:</p>
<pre>~/media/*.mp4
*.jp?g
projects/*/README</pre>
''')

files_list = _(r'''
<p>Enter multiple file paths, one per line.  It is generally possible to paste files copied from a file manager.</p>
''')

files_recursive = _(r'''
<p>Enter a directory to include all files inside it and its subdirectories, recursively.</p>
''')


fields_section = _(r'''
<p>Use this section to specify ways to extract 'fields' from source file paths.  When renaming, fields are used to make the destination file path.  Add a source of fields by selecting a type from the dropdown.</p>

<p>Field sources always operate on absolute, expanded, normalised paths (eg. on Windows, <i>~/my//docs/</i> might become <i>C:\Users\user\my\docs</i>).</p>
''')

fields_component = _(r'''
<p>Split the source file path into its components (eg. <i>/some/file/path</i> has components <i>some</i>, <i>file</i> and <i>path</i>) and create a field from one.</i>

<p>The first text entry decides which component to use, using a number starting from <b>0</b>.  Negative numbers start from the end of the path: <b>-1</b> is the base file or directory name.  Component <b>0</b> is the drive, if any (eg. <i>C:</i> on Windows).</p>

<p>The second text entry is gives the field name.</p>
''')

fields_regex = _(r'''
<p>Produce fields from groups captured by a regular expression.</p>

<p>The first text entry contains a (<a href="https://docs.python.org/3/library/re.html#regular-expression-syntax">Python flavour</a>) regular expression.  It is matched against the file or directory name, not the whole path.  Case is ignored, and the pattern is not implicitly anchored (eg. <i>tf</i> matches <i>testfile</i>).</p>

<p>The dropdown allows choosing which part of the path the pattern is matched against.  When matching against multiple path components, the system path separator is used (<b>\</b> on Windows (which will have to be escaped), <b>/</b> elsewhere.</p>

<p>The second text entry gives the field names for positional groups.  The value entered is a prefix &ndash; for example, if there are three groups and the value is <i>testfield</i>, the strings captured will be placed in fields called <i>testfield1</i>,  <i>testfield2</i> and <i>testfield3</i>, and the entire match is placed in a field called <i>testfield</i>.</p>

<p>Field names may also be placed directly in the pattern using <code>?P&lt;name&gt;</code> &ndash; for example, <code>(?P&lt;start&gt;.*)-(?P&lt;end&gt;.*)</code> gives two fields, called <i>start</i> and <i>end</i>.</p>
''')

fields_ordering = _(r'''
<p>Order all source files alphabetically and use the position in the sorted list as a field.  The dropdown allows choosing which part of the path is used for sorting.  The text entry gives the field name.</p>
''')


template = _(r'''
<p>Use this section to determine the destination file paths using a template.  The template gives the path for each file, substituting the different values of fields in each case.</p>

<p>Substitute a field's value using <code>$fieldname</code>, or <code>${fieldname}</code> if this might be ambiguous.  To use a literal <code>$</code> symbol, write <code>$$</code>.</p>

<p>The template gives a full path, so path separators can be used; intermediate directories that don't already exist are created.  If the path is relative, it is relative to the directory the program was started in.</p>

<p>For example: <code>../${program}_test/$version.tar.gz</code>.</p>
''')


cwd_section = _(r'''
<p>The base directory for all relative paths used in the 'Files' and 'Output Template' sections.  For example, if the working directory is set to <i>/some/dir</i>, then the path <i>../test.txt</i> means <i>/some/test.txt</i>.</p>
''')


preview_renames = _(r'''
<p>This view shows rename operations that will happen with the current settings.  It updates as you make changes, so if it's empty it may be that none of your file sources match any files.</p>

<p>The listing is not ordered, and if there are a lot of files to rename, not all of them are shown.</p>
''')

preview_warnings = _(r'''
<p>This view shows problems with the current settings.  The output updates as you make changes, and every rename operation is checked, even those not shown in the 'Preview' view.</p>

<p>Warnings are grouped by type, and details are only shown for a few files for each type of warning.  In some cases, when a problem is found with a particular rename operation, no further checks are made, so some possible warnings may not even be included in the total counts given for each warning type.</p>
''')

preview_fields = _(r'''
<p>This view shows the names of all fields given by existing field sources.  When fields given by different sources have the same name, the name is shown in red.  The value given when trying to use such fields in the output template is not defined.</p>
''')
