"""Diagnostic related stuffs."""

from typing import (
    NamedTuple, List, Mapping, Optional, TextIO, Dict, Iterable, TYPE_CHECKING
)
from enum import Enum
from contextlib import contextmanager
from sys import stderr

from acaciamc.utils.ansi import AnsiColor, AnsiStyle, ansi
from acaciamc.utils.str_template import STArgument, substitute

if TYPE_CHECKING:
    from acaciamc.reader import SourceRange, Reader

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
    source: "SourceRange"
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
        self.line_num_width = 5
        self.message_styles = (AnsiStyle.BOLD,)
        self.highlight_src_styles = (AnsiColor.YELLOW,)

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
        with ansi(file, *self.message_styles):
            file.write(f"{diag.source.to_str()}: ")
            with ansi(file, diag.kind.color):
                file.write(f"{diag.kind.display}: ")
            file.write(diag.format_message())
        file.write(f" [{diag.id}]\n")
        first_ln, first_col = diag.source.begin.pos
        last_ln, last_col = diag.source.end.pos
        # Make column number 0-indexed
        first_col -= 1
        last_col -= 1
        for i, line in enumerate(diag.source.get_lines(), start=first_ln):
            file.write(f"{i:>{self.line_num_width}} | ")
            is_first = i == first_ln
            is_last = i == last_ln
            if is_first:
                file.write(line[:first_col])
                highlight_start = first_col
            else:
                highlight_start = 0
            if is_last:
                highlight_end = last_col
            else:
                highlight_end = None
            with ansi(file, *self.highlight_src_styles):
                file.write(line[highlight_start:highlight_end])
            if is_last:
                file.write(line[last_col:])
            file.write("\n")
        file.write(" " * self.line_num_width + " |\n")

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
    'unclosed-font': 'Unclosed font specifier',
    'invalid-font': 'Invalid font specifier: ${font}',
    'invalid-unicode-escape': 'Invalid \\${char raw} escape',
    'unclosed-quote': 'Unclosed double quote',
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
    'invalid-func-port': 'This type of function cannot use qualifier ${port}',
    'const-new-method': "'new' methods cannot be compile time function",
    'non-static-const-method': 'Non-static method cannot be compile time '
        'function',
    'invalid-var-def': 'Variable declaration target must be an identifier',
    'positional-arg-after-keyword': 'Positional argument follows keyword '
        'argument',
    'multiple-new-methods': "Found ${nnews} 'new' methods in the same "
        "template; at most 1 expected",
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
    'multiple-new-methods-note': "Another 'new' method definition",
    # From post AST visitor
    'imported-here': "Imported here",
    'name-redefinition-note': "Previous definition here",
})
