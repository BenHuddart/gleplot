# Opening GLE Files

`gleplot.open_gle` reads a `.gle` file back into a `Figure`, which you can
change and save again like any figure you built in Python.

## Opening a file

```python
import gleplot as glp

fig = glp.open_gle('figure.gle')
ax = fig.axes[0]               # the axes, in the order of the graph blocks
ax.set_title('Revised title')
fig.savefig('figure_revised.gle')
```

`data` references in the file are resolved relative to the file's own
directory. `open_gle` also accepts GLE source text instead of a path. Its data files are
then looked up in the current directory, or in `base_dir` if you pass one:

```python
fig = glp.open_gle(source_text, base_dir='results/')
```

## Files gleplot wrote

A file gleplot wrote opens into a figure that draws the same thing. Saving it
again without changes writes the same `.gle` script and the same `.dat` files,
byte for byte. A few settings come back in an equivalent form rather than as
you set them: axis limits that were derived from the data come back as
explicit limits, and a legend placed with `legend(loc=...)` comes back as the
automatic legend at that position.

gleplot marks its own files with a metadata header (the
`! gleplot-meta-begin` comment block), which also records settings GLE has
no command for, such as shared axes, the style's default line width and
colours, and which graphs are `add_axes` insets. Files from older releases carry
version `v1` of that header and still open. Their graph geometry was
implicit, so the first save writes each axes' position explicitly and
updates the header to `v2`, a one-time change in layout. A header version
gleplot does not know is read anyway, with a note.

## Hand-written files

A file written by hand, or edited after gleplot wrote it, is read as far as
gleplot can model it. Datasets, axes settings, titles, legends and the other
commands gleplot itself writes become the corresponding parts of the figure.
GLE that gleplot does not model is kept as it was and written back in place
when you save, so it still reaches GLE, but you cannot edit it through the
Python API. Raw GLE between two graph blocks stays after the first of them,
so an `xg()` or `yg()` in it still addresses that graph. A command gleplot
models is rewritten from the figure, so a `! comment` at the end of its line
is not written back; each such comment gets a `structure` note.

A data file that gleplot did not write is never rewritten. Lines, error
bars, fills and plain `bar dN fill COLOR` bars drawn from it become
[file-based series](FILE_BASED_SERIES.md) that read the file in place. A
`bar` command that a file reference cannot express (a `width`, a group such
as `bar d1,d2`, a stack with `from`, a pattern, ...) is kept as raw GLE with
a `structure` note, and so is every bar that shares its `data` statement.
A `data` statement with an option gleplot does not read, such as
`delimiters` or an `ignore` or `numrows` count that is not a plain number,
is kept as raw GLE with a `data` note, together with every line that reads
its datasets, including a `let` and whatever draws its result. When a
`data` statement kept as raw GLE reads a data file gleplot wrote, and saving
would rewrite that file with different contents, the file is treated as one
gleplot did not write, with a `data` note, so the statement still reads the
columns it named.

Each place where gleplot had to keep something as raw GLE, or had to guess,
is recorded as a recovery note. The notes are grouped by category:

| category | what it means |
|---|---|
| `metadata` | the metadata header is old or unknown (see above) |
| `structure` | a command or option gleplot reads but cannot model, kept as raw GLE, or a comment after a modelled command, which is not kept |
| `data` | a data file or column could not be loaded, or a dataset was converted |
| `legend` | a legend was assumed, or a `key` option could not be modelled |
| `layout` | the subplot grid or shared axes were guessed, or graph geometry was kept as raw GLE |
| `smooth` | smoothing differs between series in a way the figure cannot express |
| `programmatic` | the file uses GLE programming (`sub`, `if`, `for`, `while`, ...); saving may restructure it |

`open_gle` raises each note as a `UserWarning` whose text is
`"category: message"`. To open a file you have already checked without
them, wrap the call:

```python
import warnings

import gleplot as glp

with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    fig = glp.open_gle('figure.gle')
```

To get the notes as data instead, call `gleplot.parser.parse_gle_figure`,
which returns the figure and the notes without warning:

```python
from gleplot.parser import parse_gle_figure

result = parse_gle_figure('figure.gle')
fig = result.figure
for note in result.notes:
    print(note.category.value, note.source_span, note.message)
```

`note.source_span` is the `(first, last)` line range in the original file
where gleplot can tell, otherwise `None`. `result.warnings` is the same notes
as `"category: message"` strings.

Before you overwrite a hand-written file, save to a new name, compile both,
and compare them.
