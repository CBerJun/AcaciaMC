"""Diagnostic related stuffs."""

from typing import (
    NamedTuple, List, Mapping, Optional, TextIO, Dict, Iterable, Sequence,
    TYPE_CHECKING
)
from enum import Enum
from contextlib import contextmanager
from sys import stderr

from acaciamc.utils.ansi import AnsiColor, AnsiStyle, ansi, ansi_styles_to_str
from acaciamc.utils.str_template import STArgument, substitute

if TYPE_CHECKING:
    from acaciamc.reader import Reader, FileEntry, LineColRange

class DiagnosticKind(Enum):
    """Kind of diagnostic."""

    ERROR = 0, "error", AnsiColor.RED
    WARNING = 1, "warning", AnsiColor.MAGENTA
    NOTE = 2, "note", AnsiColor.CYAN

    display: str
    color: AnsiColor
    # `registry` is a mapping from all diagnostic IDs of this kind to
    # their corresponding message template.
    registry: Dict[str, str]

    def __new__(cls, code: int, display: str, color: AnsiColor):
        obj = object.__new__(cls)
        obj._value_ = code
        obj.display = display
        obj.color = color
        obj.registry = {}
        return obj

_diag_kind_memo: Dict[str, DiagnosticKind] = {}

def diagnostic_kind(x: str) -> DiagnosticKind:
    """Get kind of a diagnostic ID."""
    res = _diag_kind_memo.get(x)
    if res is None:
        for k in DiagnosticKind:
            if x in k.registry:
                _diag_kind_memo[x] = res = k
                break
        else:
            assert False, f"invalid diagnostic ID {x}"
    return res

class Diagnostic(NamedTuple):
    """Represents a diagnostic message."""

    id: str
    source_file: "FileEntry"
    # The "primary" source location. Its starting position is the source
    # position we display to the user:
    source_range: "LineColRange"
    # The "secondary" source location(s). They only serve as notes and
    # are displayed in source code using a different indicator from the
    # primary range. All ranges may not overlap with each other or the
    # primary range:
    secondary_ranges: Sequence["LineColRange"] = ()
    args: Mapping[str, STArgument] = {}

    @property
    def kind(self) -> DiagnosticKind:
        return diagnostic_kind(self.id)

    def format_message(self) -> str:
        """Format just the message (without source information)."""
        return substitute(self.kind.registry[self.id], self.args)

class _CaptureResult:
    """See `DiagnosticsManager.capture_errors`."""
    def __init__(self):
        self.got_error = False

class _DiagnosticDump:
    """Helper for `DiagnosticsManager.dump_diagnostic`."""

    MIN_LINE_NUM_WIDTH = 5
    MIN_LINE_NUM_LEFT_PADDING = 1
    PRIMARY_SRC_STYLES = (AnsiColor.YELLOW,)
    SECONDARY_SRC_STYLES = (AnsiColor.GREEN,)
    PRIMARY_INDICATOR = '^'
    SECONDARY_INDICATOR = '~'

    def __init__(self, diag: Diagnostic, file: TextIO):
        self.diag = diag
        self.file = file
        # Display the message line...
        (primary_ln, primary_col), _ = diag.source_range
        with ansi(file, AnsiStyle.BOLD):
            file.write(
                f"{diag.source_file.display_name}:{primary_ln}:{primary_col}: "
            )
            with ansi(file, diag.kind.color):
                file.write(f"{diag.kind.display}: ")
            file.write(diag.format_message())
        file.write(f" [{diag.id}]\n")
        # Display the source code and indicators...
        self.ranges = list(diag.secondary_ranges)
        self.ranges.append(diag.source_range)
        self.ranges.sort()
        self.range_index = 0
        (first_ln, _), _ = self.ranges[0]
        _, (self.last_ln, _) = self.ranges[-1]
        source_lines = diag.source_file.get_lines(first_ln, self.last_ln)
        line_num_width = max(
            self.MIN_LINE_NUM_WIDTH,
            len(str(self.last_ln)) + self.MIN_LINE_NUM_LEFT_PADDING
        )
        indicator_line_begin = " " * line_num_width + " | "
        self.indicator_begin, indicator_end \
            = ansi_styles_to_str(diag.kind.color)  # Indicator color
        self.next_range()
        for i, self.line in enumerate(source_lines, start=first_ln):
            self.indicator_line: List[str] = [indicator_line_begin]
            self.col = 0
            self.got_highlighted = False
            file.write(f"{i:>{line_num_width}} | ")
            # Continued range...
            if self.l1 < i:
                if self.l2 > i:
                    # Continued range the covers this line completely
                    self.add_highlighted(len(self.line))
                else:
                    # Continued range ending on this line...
                    assert self.l2 == i
                    self.add_highlighted(self.c2)
                    self.next_range()
            # Ranges starting on this line...
            while self.l1 == i:
                self.add_non_highlighted(self.c1)
                self.add_highlighted(
                    self.c2 if self.l2 == i else len(self.line)
                )
                # If the range did not finish, we break and don't call
                # `self.next_range`:
                if self.l2 > i:
                    break
                self.next_range()
            # There may be some non-highlighted text left on this line
            if self.col < len(self.line):
                file.write(self.line[self.col:])
            # Don't forget to turn off the ANSI color of indicators:
            self.indicator_line.append(indicator_end)
            # Attach the indicator line to `file`
            file.write("\n" + "".join(self.indicator_line) + "\n")

    def next_range(self):
        if self.range_index >= len(self.ranges):
            # Imagine there is a final range that lies outside the
            # lines we retrieved.
            self.l1 = self.last_ln + 1
            return
        r = (self.l1, self.c1), (self.l2, self.c2) \
            = self.ranges[self.range_index]
        # Make column numbers 0-indexed
        self.c1 -= 1
        self.c2 -= 1
        self.indicator_char, self.src_styles = (
            (self.PRIMARY_INDICATOR, self.PRIMARY_SRC_STYLES)
            if r == self.diag.source_range
            else (self.SECONDARY_INDICATOR, self.SECONDARY_SRC_STYLES)
        )
        self.range_index += 1

    def add_highlighted(self, end: int):
        if end == self.col:
            return
        if not self.got_highlighted:
            self.indicator_line.append(self.indicator_begin)
            self.got_highlighted = True
        self.indicator_line.append(self.indicator_char * (end - self.col))
        with ansi(self.file, *self.src_styles):
            self.file.write(self.line[self.col:end])
        self.col = end

    def add_non_highlighted(self, end: int):
        if end == self.col:
            return
        self.indicator_line.append(' ' * (end - self.col))
        self.file.write(self.line[self.col:end])
        self.col = end

class DiagnosticsManager:
    """Manages and prints diagnostic messages."""

    def __init__(self, reader: "Reader", stream: Optional[TextIO] = stderr):
        self.diags: List[Diagnostic] = []
        self.note_context: List[Diagnostic] = []
        self.reader = reader
        self.stream = stream

    @contextmanager
    def capture_errors(self):
        """
        Capture `DiagnosticError` and automatically log them. The value
        yielded is an object with a boolean attribute `got_error`,
        which, when accessed after the `with` statement has finished,
        tells you if an error has been captured.
        """
        cr = _CaptureResult()
        try:
            yield cr
        except DiagnosticError as err:
            cr.got_error = True
            self.push_diagnostic(err.diag, err.notes)

    @contextmanager
    def using_note(self, note: Diagnostic):
        """
        Add the given note to WARNING or ERROR diagnostics that are
        issued in this context. This can be nested, and the most recent
        one appears first.
        """
        assert note.kind is DiagnosticKind.NOTE
        self.note_context.append(note)
        try:
            yield
        except DiagnosticError as err:
            # When this error reaches `capture_errors`, this note would
            # have been popped out of `self.note_context`, and thus the
            # notes will not apply. To fix this we manually add this
            # note to that error and reraise it.
            err.add_note(note)
            raise
        finally:
            self.note_context.pop()

    def push_diagnostic(self, diag: Diagnostic,
                        notes: Optional[Iterable[Diagnostic]] = None):
        """
        Add a diagnostic, optionally with some notes. The main
        diagnostic will appear first, then the given `notes`, then the
        notes added using `using_note`. If the given `diag` is itself
        a note then notes specified by `using_note` will not be added.
        """
        self.diags.append(diag)
        self.dump_diagnostic(diag)
        if notes is not None:
            for note in notes:
                assert note.kind is DiagnosticKind.NOTE
                self.push_diagnostic(note)
        if diag.kind is not DiagnosticKind.NOTE:
            # Apply notes added by `using_note`
            for note in reversed(self.note_context):
                self.push_diagnostic(note)

    def dump_diagnostic(self, diag: Diagnostic, file: Optional[TextIO] = None):
        """
        Print the given `diag` to `file`. File defaults to
        `self.stream`. `diag` must be a diagnostic that was added to
        this manager.
        """
        file = self.stream if file is None else file
        if file is None:
            return
        _DiagnosticDump(diag, file)

class DiagnosticError(Exception):
    """Raised to issue an ERROR diagnostic and stop compilation."""

    def __init__(self, diag: Diagnostic):
        super().__init__(diag)
        assert diag.kind is DiagnosticKind.ERROR
        self.diag = diag
        self.notes: List[Diagnostic] = []

    def add_note(self, note: Diagnostic):
        self.notes.append(note)

DiagnosticKind.ERROR.registry.update({
    # From tokenizer
    'invalid-char': 'Invalid character ${char}',
    'unmatched-bracket': 'Unmatched ${char}',
    'unmatched-bracket-pair': 'Closing bracket ${close} does not match '
        'opening bracket ${open}',
    'unclosed-fexpr': 'Unclosed formatted expression',
    'unclosed-long-comment': 'Unclosed multi-line comment',
    'unclosed-long-command': 'Unclosed multi-line command',
    'unclosed-bracket': 'Unclosed ${char}',
    'eof-after-continuation': 'Found end of file after line continuation',
    'char-after-continuation': 'Unexpected character after line continuation',
    'interface-path-expected': "A path is expected after 'interface'",
    'invalid-dedent': 'Dedent does not match any outer indentation level',
    'integer-expected': 'Expected base ${base} integer',
    'invalid-number-char': 'Invalid character ${char} in base ${base} number',
    'unclosed-font': 'Unclosed font specifier',
    'invalid-font': 'Invalid font specifier: ${font}',
    'incomplete-unicode-escape': 'Incomplete \\${char raw} Unicode escape',
    'invalid-unicode-code-point': 'Invalid Unicode code point U+${code raw}; '
        'code points cannot be larger than or equal to 0x110000',
    'unclosed-quote': 'Unclosed double quote',
    'incomplete-escape': 'Expect a character after backslash escape, found '
        'end of file',
    'invalid-escape': 'Invalid escape sequence \\${character raw}; consider '
        'doubling the backslash?',
    'integer-literal-overflow': 'Integer literal overflows; it must be in the '
        'range of a 32-bit signed integer',
    # From parser
    'unexpected-token': 'Unexpected token ${token}',
    'empty-block': 'Expect an indented block',
    'non-default-arg-after-default': 'Non-default argument ${arg} follows '
        'default argument',
    'dont-know-arg-type': 'Type of argument ${arg} or its default value must '
        'be specified',
    'duplicate-arg': 'Duplicate argument ${arg} in function definition',
    'duplicate-keyword-args': 'Duplicate keyword argument ${arg} in function '
        'call',
    'invalid-valpassing': 'Qualifier ${qualifier} cannot be used in a '
        '${func-type raw}',
    'const-new-method': "'new' methods cannot be compile time function",
    'non-static-const-method': 'Non-static method cannot be compile time '
        'function',
    'positional-arg-after-keyword': 'Positional argument follows keyword '
        'argument',
    'multiple-new-methods': "Found multiple 'new' methods in the same "
        "template; at most 1 expected",
    'duplicate-entity-attr': "Found multiple entity attributes of name "
        "${name} in the same template",
    'duplicate-struct-attr': "Found multiple fields of name ${name} in the "
        "same struct",
    'return-scope': "'return' outside function or interface",
    'interface-return-value': "Cannot return a value from an interface",
    # From post AST visitor
    'module-not-found': "Module ${module} is not found",
    'undefined-name': "Name ${name} is not defined",
    'name-redefinition': "Redefinition of name ${name}",
    'cannot-import-name': "Cannot import name ${name} from module ${module}",
})
DiagnosticKind.WARNING.registry.update({
    # From tokenizer
    'new-font': 'The font specifier ${font} is a Minecraft 1.19.80 feature',
    # From post AST visitor
    'unused-name': 'Name ${name} is defined but not used',
    'partial-wildcard-import': 'Wildcard import on partially initialized '
        'module ${module} may result in some names not being imported'
})
DiagnosticKind.NOTE.registry.update({
    # From parser
    'multiple-new-methods-note': "Previous 'new' method definition here",
    'duplicate-entity-attr-note': "Previous definition here",
    'duplicate-struct-attr-note': "Previous definition here",
    # From post AST visitor
    'imported-here': "Imported here",
    'name-redefinition-note': "Previous definition here",
})
