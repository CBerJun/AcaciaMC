"""Diagnostic related stuffs."""

from typing import (
    NamedTuple, List, Mapping, Optional, TextIO, Dict, Iterable, TYPE_CHECKING
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
    source_range: "LineColRange"
    args: Mapping[str, STArgument]

    @property
    def kind(self) -> DiagnosticKind:
        return diagnostic_kind(self.id)

    def format_message(self) -> str:
        """Format just the message (without source information)."""
        return substitute(self.kind.registry[self.id], self.args)

class DiagnosticsManager:
    """Manages and prints diagnostic messages."""

    def __init__(self, reader: "Reader", stream: Optional[TextIO] = stderr):
        self.diags: List[Diagnostic] = []
        self.note_context: List[Diagnostic] = []
        self.reader = reader
        self.stream = stream
        self.min_line_num_width = 5
        self.min_line_num_left_padding = 1
        self.message_styles = (AnsiStyle.BOLD,)
        self.highlight_src_styles = (AnsiColor.YELLOW,)
        self.primary_indicator = '^'

    @contextmanager
    def capture_errors(self):
        """Capture `DiagnosticError` and automatically log them."""
        try:
            yield
        except DiagnosticError as err:
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
        (first_ln, first_col), (last_ln, last_col) = diag.source_range
        with ansi(file, *self.message_styles):
            file.write(
                f"{diag.source_file.display_name}:{first_ln}:{first_col}: "
            )
            with ansi(file, diag.kind.color):
                file.write(f"{diag.kind.display}: ")
            file.write(diag.format_message())
        file.write(f" [{diag.id}]\n")
        # Make column number 0-indexed
        first_col -= 1
        last_col -= 1
        source_lines = diag.source_file.get_lines(first_ln, last_ln)
        line_num_width = max(
            self.min_line_num_width,
            len(str(last_ln)) + self.min_line_num_left_padding
        )
        indicator_line_begin = " " * line_num_width + " | "
        for i, line in enumerate(source_lines, start=first_ln):
            indicator_line: List[str] = [indicator_line_begin]
            file.write(f"{i:>{line_num_width}} | ")
            is_first = i == first_ln
            is_last = i == last_ln
            if is_first:
                file.write(line[:first_col])
                indicator_line.append(" " * first_col)
                highlight_start = first_col
            else:
                highlight_start = 0
            if is_last:
                highlight_end = last_col
            else:
                highlight_end = len(line)
            with ansi(file, *self.highlight_src_styles):
                file.write(line[highlight_start:highlight_end])
            ic_begin, ic_end = ansi_styles_to_str(diag.kind.color)
            indicator_line.append(ic_begin)
            indicator_line.append(
                self.primary_indicator * (highlight_end - highlight_start)
            )
            indicator_line.append(ic_end)
            if is_last:
                file.write(line[last_col:])
            file.write("\n" + "".join(indicator_line) + "\n")

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
