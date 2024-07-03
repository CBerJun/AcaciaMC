"""Tokenizer (Lexer) for Acacia."""

from typing import (
    Union, List, TextIO, Tuple, Dict, Optional, NamedTuple, Any, Callable,
    Generator, Mapping, TYPE_CHECKING
)
from contextlib import contextmanager
from string import ascii_letters, digits
import enum
import string

from acaciamc.reader import SourceRange, SourceLocation
from acaciamc.utils.str_template import STInt, STStr, STArgument
from acaciamc.diagnostic import Diagnostic, DiagnosticError

if TYPE_CHECKING:
    from acaciamc.reader import FileEntry
    from acaciamc.diagnostic import DiagnosticsManager

UNICODE_ESCAPES = {'x': 2, 'u': 4, 'U': 8}
# These are the only characters allowed in function paths.
FUNCTION_PATH_CHARS = frozenset(ascii_letters + digits + ".(-)_/")
# Color codes
COLORS = {
    "black": "0",
    "dark_blue": "1",
    "dark_green": "2",
    "dark_aqua": "3",
    "dark_red": "4",
    "dark_purple": "5",
    "gold": "6",
    "gray": "7",
    "dark_gray": "8",
    "blue": "9",
    "green": "a",
    "aqua": "b",
    "red": "c",
    "light_purple": "d",
    "yellow": "e",
    "white": "f",
    "minecoin_gold": "g",
}
# 1.19.80+ colors
COLORS_NEW = {
    "material_quartz": "h",
    "material_iron": "i",
    "material_netherite": "j",
    "material_redstone": "m",
    "material_copper": "n",
    "material_gold": "p",
    "material_emerald": "q",
    "material_diamond": "s",
    "material_lapis": "t",
    "material_amethyst": "u",
}
FONTS = {
    "reset": "r",
    "bold": "l",
    "italic": "o",
    "obfuscated": "k",
}

class TokenType(enum.Enum):
    """
    Token types.
    Value convension:
    1. If length of value is 1 or 2 and the first character is not an
    identifier character ([a-zA-Z0-9_]) or anything special (like '#'),
    then a token is registered automatically. (e.g. '=' or '->')
    2. If value is defined between `true` and `false`, then it is
    registered as a keyword.
    """
    # block
    indent = 'INDENT'
    dedent = 'DEDENT'
    new_line = 'NEW_LINE'
    lparen = '('
    rparen = ')'
    lbracket = '['
    rbracket = ']'
    lbrace = '{'
    rbrace = '}'
    colon = ':'
    comma = ','
    end_marker = 'END_MARKER'  # end of file
    # command and string
    command_begin = 'COMMAND_BEGIN'
    string_begin = 'STRING_BEGIN'
    text_body = 'TEXT_BODY'  # value: str
    dollar_lbrace = 'DOLLAR_LBRACE'
    command_end = 'COMMAND_END'
    string_end = 'STRING_END'
    # operator
    ## binary operators
    plus = '+'
    minus = '-'
    star = '*'
    slash = '/'
    mod = '%'
    ## compare operators
    equal_to = '=='
    unequal_to = '!='
    greater = '>'
    less = '<'
    greater_equal = '>='
    less_equal = '<='
    ## augmented assign
    plus_equal = '+='
    minus_equal = '-='
    times_equal = '*='
    divide_equal = '/='
    mod_equal = '%='
    ## other
    equal = '='
    arrow = '->'
    point = '.'
    at = '@'
    walrus = ':='
    ampersand = '&'
    # expressions
    ## literal
    integer = 'INTEGER'  # value: int
    float = 'FLOAT'  # value: float
    interface_path = 'INTERFACE_PATH'  # value: str
    ## id
    identifier = 'IDENTIFIER'  # value: str
    # keywords
    true = 'True'  # must at beginning of keyword part
    def_ = 'def'
    interface = 'interface'
    inline = 'inline'
    entity = 'entity'
    extends = 'extends'
    self = 'self'
    if_ = 'if'
    elif_ = 'elif'
    else_ = 'else'
    while_ = 'while'
    pass_ = 'pass'
    and_ = 'and'
    or_ = 'or'
    not_ = 'not'
    result = 'result'
    import_ = 'import'
    as_ = 'as'
    from_ = 'from'
    none = 'None'
    for_ = 'for'
    in_ = 'in'
    struct = 'struct'
    virtual = 'virtual'
    override = 'override'
    const = 'const'
    static = 'static'
    new = 'new'
    false = 'False'  # must at end of keyword part

KEYWORDS: Dict[str, TokenType] = {}
def _kw_builder():
    # NOTE this relies on that keywords in `TokenType` enum are all
    # between `true` and `false`.
    token_types = tuple(TokenType)
    for i in range(
        token_types.index(TokenType.true),
        token_types.index(TokenType.false) + 1
    ):
        token_type = token_types[i]
        KEYWORDS[token_type.value] = token_type
_kw_builder()
del _kw_builder

BRACKETS = {
    TokenType.lparen: TokenType.rparen,
    TokenType.lbracket: TokenType.rbracket,
    TokenType.lbrace: TokenType.rbrace
}
RB2LB = {v: k for k, v in BRACKETS.items()}

def is_idstart(c: str) -> bool:
    """Return if given character can start an identifier in Acacia."""
    return c.isalpha() or c == '_'

def is_idcontinue(c: str) -> bool:
    """Return if given character is valid in an Acacia identifier."""
    return is_idstart(c) or c in string.digits

class Token(NamedTuple):
    """
    A token with `type` type that ranges from before the character
    pointed by `pos1` to before the character pointed by `pos2`. The
    payload `value` defaults to None. Line and column numbers are
    1-indexed (just like all other places).
    """

    type: TokenType
    pos1: Tuple[int, int]  # lineno, col
    pos2: Tuple[int, int]
    value: Any = None

    def __repr__(self) -> str:
        if self.value is None:
            value_str = ''
        else:
            value_str = f'({self.value!r})'
        return '<Token %s%s at %d:%d-%d:%d>' % (
            self.type.name, value_str,
            *self.pos1, *self.pos2
        )

    def to_source_range(self, file_entry: "FileEntry") -> SourceRange:
        return file_entry.get_range(self.pos1, self.pos2)

    def display_string(self) -> str:
        """Get a string representation to display to user."""
        v = self.type.value
        if not v.isupper():
            # Add quotes to symbols or keywords
            v = repr(v)
        return v

class _FormattedStrManager:
    """
    This object is created by `Tokenizer` to indicate that we are now
    parsing some literal text that could contain formatted expression
    like ${this}. It collects all the text portions (`add_text`), and
    when end of the literal text is reached *or* an ${interpolation}
    is found, `retrieve_text_token` will be called to dump all the texts
    we have collected. Then when we leave the ${interpolation} texts
    start to accumulate again, etc.
    """

    def __init__(self, start_token: Token):
        self.texts: List[str] = []
        self.text_pos: Optional[Tuple[int, int]] = None
        # The `start_token` is not used by us, but `Tokenizer` uses it
        # to track where the we start in source.
        self.start_token = start_token
        # This is not used by us, but by `Tokenizer`:
        self.last_dollar_lbrace: Optional[Token] = None

    def add_text(self, text: str, pos: Tuple[int, int]) -> None:
        if self.text_pos is None:
            self.text_pos = pos
        self.texts.append(text)

    def retrieve_text_token(self, pos: Tuple[int, int]) -> Optional[Token]:
        if not self.texts:
            return None
        assert self.text_pos is not None
        tok = Token(TokenType.text_body, self.text_pos, pos,
                    value=''.join(self.texts))
        self.texts.clear()
        self.text_pos = None
        return tok

class _BracketFrame(NamedTuple):
    """A frame that represents an opening bracket."""

    type: TokenType
    # We assume that every bracket is 1-character long and `pos` points
    # to that character.
    pos: Tuple[int, int]
    cmd_fexpr: bool = False
    str_fexpr: bool = False

class Tokenizer:
    def __init__(self, src: TextIO, file_entry: "FileEntry",
                 diagnostic_manager: "DiagnosticsManager",
                 mc_version: Tuple[int, ...]):
        self.src = src
        self.file_entry = file_entry
        self.diagnostic_manager = diagnostic_manager
        self.mc_version = mc_version
        self.current_char = ''
        self.current_lineno = 0
        self.current_col = 0
        self.position = 0  # string pointer
        self.buffer_tokens: List[Token] = []
        self.bracket_stack: List[_BracketFrame] = []
        self.indent_record: List[int] = [0]
        # Indicates if this logical line has produced token:
        self.has_content = False
        # Indicates if current line is continued from last line:
        self.last_line_continued = False
        # Indicates if we are in a command (single or multi-line):
        self.inside_command: Optional[_FormattedStrManager] = None
        # Indicates if it's multi-line command (exists only if
        # `inside_command` is not None):
        self.continued_command = False
        # Indicates if we are in a formatted expression of command:
        self.in_command_fexpr = False
        # Track nested string literal like "1${"2${"3"}"}":
        self.string_stack: List[_FormattedStrManager] = []
        # Indicates if we are in formatted expression of the most inner
        # string (we must be in fexpr of any outer string since this is
        # the only way you could put a string literal inside another):
        self.in_string_fexpr = False
        # Indicates if we are in multi-line comment:
        self.continued_comment = False
        # Records pos of start of long comment (pos before "#*"). Exists
        # iff continued_comment is True:
        self.continued_comment_pos: Optional[Tuple[int, int]] = None
        # Indicate if the last token was INTERFACE:
        self.last_is_interface = False

    @property
    def current_pos(self) -> Tuple[int, int]:
        return self.current_lineno, self.current_col

    @property
    def currnet_location(self) -> SourceLocation:
        return self.file_entry.get_location(self.current_pos)

    def error(self, diag_id: str, pos: Optional[Tuple[int, int]] = None,
              args: Optional[Mapping[str, STArgument]] = None):
        """Raise an ERROR diagnostic on a specific location in source."""
        if pos is None:
            pos = self.current_pos
        location = self.file_entry.get_location(pos)
        loc_range = SourceRange(location, location)
        self.error_range(diag_id, loc_range, args)

    def error_range(
        self, diag_id: str, rng: SourceRange,
        args: Optional[Mapping[str, STArgument]] = None
    ):
        """Raise an ERROR diagnostic on a range in source."""
        if args is None:
            args = {}
        raise DiagnosticError(Diagnostic(id=diag_id, source=rng, args=args))

    def forward(self):
        """Read next char and push pointer."""
        if self.position >= self.line_len:
            self.current_char = None
            self.current_col = self.line_len + 1
        else:
            self.current_char = self.current_line[self.position]
            self.position += 1
            self.current_col += 1

    def peek(self, offset=0):
        """Peek the following char without pushing pointer."""
        pos = self.position + offset
        if pos < self.line_len:
            return self.current_line[pos]
        return None

    def get_next_token(self):
        """Get the next token."""
        while not self.buffer_tokens:
            self.buffer_tokens = self.parse_line()
        return self.buffer_tokens.pop(0)

    def parse_line(self) -> List[Token]:
        """Parse a line."""
        self.current_line = self.src.readline()
        self.line_len = len(self.current_line)
        self.current_lineno += 1
        self.current_col = 0
        self.position = 0
        res: List[Token] = []
        self.forward()
        # read indent
        if not (self.continued_command
                or self.continued_comment
                or self.last_line_continued
                or self.bracket_stack):
            # Generate indent token if this is not a continued line
            # (start of a new logical line).
            self.has_content = False
            prespaces = 0
            while self.current_char == ' ':
                prespaces += 1
                self.forward()
        else:
            prespaces = -1
            if self.continued_comment:
                self.handle_long_comment()
        while True:
            if self.inside_command and not self.in_command_fexpr:
                if self.continued_command:
                    res.extend(self.handle_long_command())
                    # If dollar lbrace is not closed, then the long
                    # command should not have ended. Instead the
                    # tokenizer would keep tokenizing as normal.
                    # e.g. `/* ${ */` results in unexpected token '*'.
                else:
                    res.extend(self.handle_command())
            if self.string_stack and not self.in_string_fexpr:
                res.extend(self.handle_string())
            # skip spaces
            self.skip_spaces()
            # check end of line
            if self.current_char in ("\n", "\\", None):
                break
            # comment
            if self.current_char == "#":
                if self.peek() == "*":
                    self.continued_comment_pos = self.current_pos
                    self.forward()
                    self.forward()
                    self.handle_long_comment()
                    continue
                else:
                    self.skip_comment()
                    break
            # start
            ## path after `interface` keyword
            if self.last_is_interface:
                if self.current_char == '"':
                    # Quoted path
                    with self.make_string_begin() as gettok:
                        self.forward()  # skip '"'
                    res.append(gettok())
                else:
                    # Unquoted path
                    res.append(self.handle_interface_path())
                self.last_is_interface = False
                continue
            ## special tokens
            ok = True
            if self.current_char in string.digits:
                res.append(self.handle_number())
            elif is_idstart(self.current_char):
                id_token = self.handle_name()
                res.append(id_token)
                # Special case: `interface` keyword, since after it goes
                # a path.
                if id_token.type is TokenType.interface:
                    self.last_is_interface = True
            elif self.current_char == '/' and not (self.has_content or res):
                # Only read when "/" is first token of this logical line.
                with self.make_token(TokenType.command_begin) as gettok:
                    self.forward()  # skip "/"
                    if self.current_char == '*':
                        self.continued_command = True
                        self.forward()  # skip "*"
                command_begin = gettok()
                res.append(command_begin)
                self.inside_command = _FormattedStrManager(command_begin)
            elif self.current_char == '"':
                with self.make_string_begin() as gettok:
                    self.forward()  # skip '"'
                res.append(gettok())
            else:
                ok = False
            if ok:
                continue
            ## try two-char token
            peek = self.peek()
            if peek is not None:
                twochars = self.current_char + peek
                try:
                    token_type = TokenType(twochars)
                except ValueError:
                    pass
                else:
                    # It is indeed a two-char token!
                    with self.make_token(token_type) as gettok:
                        self.forward()
                        self.forward()
                    res.append(gettok())
                    continue
            ## try one-char token
            try:
                token_type = TokenType(self.current_char)
            except ValueError:
                # We've run out of possibilities.
                self.error_range(
                    'invalid-char', self.currnet_location.to_range(1),
                    args={'char': STStr(self.current_char)}
                )
            else:
                if token_type in BRACKETS:
                    self.bracket_stack.append(_BracketFrame(
                        token_type, self.current_pos
                    ))
                elif token_type in RB2LB:
                    if not self.bracket_stack:
                        self.error_range(
                            'unmatched-bracket',
                            self.currnet_location.to_range(1),
                            args={'char': STStr(self.current_char)}
                        )
                    expect = RB2LB[token_type]
                    got_f = self.bracket_stack.pop()
                    got = got_f.type
                    if got is not expect:
                        self.error_range(
                            'unmatched-bracket-pair',
                            self.currnet_location.to_range(1),
                            args={
                                'open': STStr(got.value),
                                'close': STStr(token_type.value),
                            }
                        )
                    if got is TokenType.lbrace:
                        if got_f.cmd_fexpr:
                            self.in_command_fexpr = False
                        elif got_f.str_fexpr:
                            self.in_string_fexpr = False
                with self.make_token(token_type) as gettok:
                    self.forward()
                res.append(gettok())
        # Now self.current_char is either '\n', '\\' or None (EOF)
        if (
            # ${} in single line command can't use implicit line continuation.
            (self.in_command_fexpr and not self.continued_command)
            # And so is ${} in string literal.
            or self.in_string_fexpr
        ):
            # Get where the last "${" is
            if self.in_command_fexpr:
                mgr = self.inside_command
            else:
                mgr = self.string_stack[-1]
            assert mgr is not None
            assert mgr.last_dollar_lbrace is not None
            src_range = mgr.last_dollar_lbrace.to_source_range(self.file_entry)
            # Throw
            self.error_range('unclosed-fexpr', src_range)
        backslash = False
        eof = False
        if res:
            self.has_content = True
        if self.current_char == '\n':
            if self.has_content and not (
                self.continued_comment or self.continued_command
                or self.bracket_stack
            ):
                with self.make_newline() as gettok:
                    self.forward()  # skip '\n'
                res.append(gettok())
            self.last_line_continued = False
        elif self.current_char is None:
            if self.continued_comment:
                assert self.continued_comment_pos
                cpos = self.file_entry.get_location(self.continued_comment_pos)
                # 2 is the length of "#*".
                self.error_range('unclosed-long-comment', cpos.to_range(2))
            if self.continued_command:
                assert self.inside_command
                if self.in_command_fexpr:
                    assert self.inside_command.last_dollar_lbrace
                    src_range = self.inside_command.last_dollar_lbrace \
                        .to_source_range(self.file_entry)
                    self.error_range('unclosed-fexpr', src_range)
                src_range = self.inside_command.start_token \
                    .to_source_range(self.file_entry)
                self.error_range('unclosed-long-command', src_range)
            if self.bracket_stack:
                br = self.bracket_stack[-1]
                # Assume that all brackets are made of just 1 character
                src_range = self.file_entry.get_location(br.pos).to_range(1)
                self.error_range(
                    'unclosed-bracket', src_range,
                    args={'char': STStr(br.type.value)}
                )
            if self.has_content:
                with self.make_newline() as gettok:
                    pass  # This NEWLINE is added implicitly, so zerowidth
                res.append(gettok())
            eof = True
        elif self.current_char == '\\':
            self.forward()  # skip "\\"
            if self.current_char is None:
                self.error('eof-after-continuation')
            if self.current_char != '\n':
                self.error_range('char-after-continuation',
                                 self.currnet_location.to_range(1))
            backslash = self.last_line_continued = True
        # Count indent: if this physical line is not a continued line,
        # and (this physical line has content or ends with backslash)
        if (res or backslash) and prespaces != -1:
            res[:0] = self.handle_indent(
                prespaces, begin_col=1,
                # Based on the fact that only spaces are allowed for
                # indentations:
                end_col=prespaces+1
            )
        # Now clean up if we reach end of file; this is delayed to be
        # done here because we still want the indent to be emitted
        # first.
        if eof:
            # Dump DEDENTs and emit END_MARKER
            res.extend(self.handle_indent(
                0, begin_col=self.current_col, end_col=self.current_col
            ))
            res.append(self.make_zerowidth_token(TokenType.end_marker))
        return res

    def make_zerowidth_token(self, tok_type: TokenType, value=None) -> Token:
        """Generate a token at `current_pos` with 0 width."""
        return Token(tok_type, self.current_pos, self.current_pos, value)

    @contextmanager
    def make_token(self, tok_type: Optional[TokenType] = None) \
            -> Generator[Callable[..., Token], None, None]:
        """
        "Make" a token. Used as a context manager.
        Return a callback that produces a `Token` whose beginning point
        is position when the context manager enters and ending point is
        the position when we exits.
        Callback accepts an optional `value` that is used as token
        value. If `tok_type` is None, callback has a required argument
        that is used as token type. 
        """
        if tok_type is None:
            # Redeclaration of `_get` causes type checker error.
            def _get(tok_type: TokenType, value=None) -> Token:  # type: ignore
                return Token(tok_type, pos1, pos2, value)
        else:
            def _get(value=None) -> Token:
                return Token(tok_type, pos1, pos2, value)
        pos1 = self.current_pos
        yield _get
        pos2 = self.current_pos

    def skip_spaces(self):
        """Skip space characters."""
        while self.current_char == ' ':
            self.forward()

    def skip_comment(self):
        """Skip a single-line # comment."""
        while self.current_char is not None and self.current_char != '\n':
            self.forward()

    @contextmanager
    def make_string_begin(self) -> Generator[Callable[[], Token], None, None]:
        self.in_string_fexpr = False
        def _my_gettok():
            return token
        with self.make_token(TokenType.string_begin) as gettok:
            yield _my_gettok
        token = gettok()
        self.string_stack.append(_FormattedStrManager(token))

    def handle_long_comment(self):
        # we want to leave current_char on next char after "#",
        # so use previous_char
        previous_char = ''
        while not (previous_char == '*' and self.current_char == '#'):
            if self.current_char in ("\n", None):
                self.continued_comment = True
                return
            previous_char = self.current_char
            self.forward()
        self.forward()  # skip char "#"
        self.continued_comment = False

    def make_newline(self):
        """Make a logical NEWLINE token and do checks."""
        if self.last_is_interface:
            self.error('interface-path-expected')
        return self.make_token(TokenType.new_line)

    def handle_indent(self, spaces: int, begin_col: int, end_col: int) \
            -> List[Token]:
        """
        Generate INDENT and DEDENT.
        Usually INDENTs and DEDENTs appear in beginning of line, with
        beginning column number 1, but when dumping DEDENTs at end of
        file, the `begin_col` could be different.
        """
        ln = self.current_lineno
        tokens = []
        if spaces > self.indent_record[-1]:
            self.indent_record.append(spaces)
            tokens.append(Token(
                TokenType.indent, (ln, begin_col), (ln, end_col)
            ))
        try:
            i = self.indent_record.index(spaces)
        except ValueError:
            self.error('invalid-dedent', (ln, begin_col))
        dedent_count = len(self.indent_record) - 1 - i
        self.indent_record = self.indent_record[:i+1]
        tokens.extend(Token(TokenType.dedent, (ln, end_col), (ln, end_col))
                        for _ in range(dedent_count))
        return tokens

    @staticmethod
    def _isdecimal(char: Union[str, None]):
        return char is not None and char in string.digits

    def handle_number(self):
        """Read an INTEGER or a FLOAT token."""
        res = []
        with self.make_token() as gettok:
            ## decide base
            base = 10
            peek = self.peek()
            if self.current_char == '0' and peek is not None:
                peek = peek.upper()
                if peek in "BOX":
                    if peek == 'B':
                        base = 2
                    elif peek == 'O':
                        base = 8
                    elif peek == 'X':
                        base = 16
                    # skip 2 chars ("0x" "0b" "0o")
                    self.forward()
                    self.forward()
            ## read
            valid_chars = '0123456789ABCDEF'[:base]
            while ((self.current_char is not None)
                and (self.current_char.upper() in valid_chars)):
                res.append(self.current_char)
                self.forward()
            ## convert string to number
            if (self.current_char == "."
                and base == 10
                and self._isdecimal(self.peek())
            ):  # float
                self.forward()
                res.append(".")
                while self._isdecimal(self.current_char):
                    res.append(self.current_char)
                    self.forward()
                value = float(''.join(res))
                tok_type = TokenType.float
            else:  # integer
                if not res:
                    self.error('integer-expected',
                            args={'base': STInt(base)})
                value = int(''.join(res), base=base)
                tok_type = TokenType.integer
        return gettok(tok_type, value)

    def handle_name(self):
        """Read a keyword or an IDENTIFIER token."""
        chars = []
        with self.make_token() as gettok:
            while (self.current_char is not None
                   and is_idcontinue(self.current_char)):
                chars.append(self.current_char)
                self.forward()
        name = ''.join(chars)
        token_type = KEYWORDS.get(name)
        if token_type is None:  # IDENTIFIER
            return gettok(TokenType.identifier, value=name)
        # Keyword
        return gettok(token_type)

    def _read_escapable_char(self) -> str:
        """
        Read current char as an escapable one (in string or command)
        and skip the read char(s). Return the handled char(s).
        NOTE Caller needs to ensure `self.current_char` is not None.
        """
        beginning_col = self.current_col
        lineno = self.current_lineno
        first = self.current_char
        assert first is not None
        self.forward()
        # not escapable
        if first != '\\':
            return first
        # escapable
        second = self.current_char
        if second == '\\':  # backslash itself
            self.forward()  # skip second backslash
            return second
        elif second == '#':  # font
            self.forward()  # skip '#'
            if self.current_char != '(':
                return '\xA7'
            res: List[str] = []
            cur_spec: List[str] = []
            self.forward()  # skip '('
            # Start of current font specifier (since we do not allow
            # line breaks in middle, we do not need to track line
            # number) Note that trailing spaces are included:
            cur_col = self.current_col
            while True:
                if self.current_char is None or self.current_char == '\n':
                    src_range = (
                        self.file_entry
                        .get_location((lineno, beginning_col))
                        .to_range(3)  # len("\\#(") == 3
                    )
                    self.error_range('unclosed-font', src_range)
                if self.current_char in (',', ')'):
                    font_withspaces = ''.join(cur_spec)
                    font = font_withspaces.strip(' ')
                    cur_spec.clear()
                    diag_id: Optional[str] = None
                    ch: Optional[str] = None
                    if font in COLORS:
                        ch = COLORS[font]
                    elif font in COLORS_NEW:
                        ch = COLORS_NEW[font]
                        if self.mc_version < (1, 19, 80):
                            diag_id = 'new-font'
                    elif font in FONTS:
                        ch = FONTS[font]
                    else:
                        diag_id = 'invalid-font'
                    if diag_id is not None:
                        # An diagnostic occured ('new-font' or
                        # 'invalid-font')
                        # Work out source range of this font specifier
                        # with spaces stripped.
                        font_ls = font_withspaces.lstrip(' ')
                        # If `font_withspaces` only consists of spaces,
                        # we have to treat specially.
                        if font_ls:
                            font_rs = font_withspaces.rstrip(' ')
                            nlspaces = len(font_withspaces) - len(font_ls)
                            nrspaces = len(font_withspaces) - len(font_rs)
                            loc1 = self.file_entry.get_location(
                                (lineno, cur_col + nlspaces)
                            )
                            loc2 = self.file_entry.get_location(
                                (lineno, self.current_col - nrspaces)
                            )
                            src_range = SourceRange(loc1, loc2)
                        else:
                            src_range = (
                                self.file_entry
                                .get_location((lineno, cur_col))
                                .to_range(0)
                            )
                    if diag_id == 'invalid-font':
                        self.error_range(
                            diag_id, src_range,
                            args={'font': STStr(font)}
                        )
                    elif diag_id is not None:
                        assert diag_id == 'new-font'
                        self.diagnostic_manager.push_diagnostic(
                            Diagnostic(
                                id=diag_id, source=src_range,
                                args={'font': STStr(font)}
                            )
                        )
                    assert ch is not None
                    res.append(f"\xA7{ch}")
                    if self.current_char == ')':
                        break
                    cur_col = self.current_col + 1
                else:
                    cur_spec.append(self.current_char)
                self.forward()
            self.forward()  # skip ')'
            return ''.join(res)
        ## NOTE '\n' should be passed directly to MC
        ## because MC use '\n' escape too
        elif second in UNICODE_ESCAPES:  # unicode number
            def _err():
                src_range = (
                    self.file_entry
                    .get_location((lineno, beginning_col))
                    .to_range(2)  # len('\\x') == 2, for example
                )
                self.error_range(
                    'invalid-unicode-escape', src_range,
                    args={'char': STStr(second)}
                )
            self.forward()  # skip UNICODE_ESCAPES character
            code = []
            length = UNICODE_ESCAPES[second]
            for _ in range(length):
                if (self.current_char is None
                        or self.current_char not in string.hexdigits):
                    _err()
                code.append(self.current_char)
                self.forward()
            unicode = int(''.join(code), base=16)
            if unicode >= 0x110000:
                _err()
            return chr(unicode)
        # when escape can't be recognized, just return "\\"
        # and the `second` char will be handled later
        return first  # (here first == '\\')

    def handle_string(self) -> List[Token]:
        """Help read a string literal."""
        mgr = self.string_stack[-1]
        while self.current_char != '"':
            # check None and \n
            if (self.current_char is None) or (self.current_char == '\n'):
                src_range = mgr.start_token.to_source_range(self.file_entry)
                self.error_range('unclosed-quote', src_range)
            if self.current_char == '\\' and self.peek() == '"':
                # special escape in strings
                mgr.add_text('"', self.current_pos)
                self.forward()
                self.forward()
                continue
            tokens = self._fexpr_unit(mgr, is_cmd=False)
            if tokens:
                return tokens
        else:
            tok = mgr.retrieve_text_token(self.current_pos)
            with self.make_token(TokenType.string_end) as gettok:
                self.forward()  # skip last '"'
            endtok = gettok()
            self.string_stack.pop()
            self.in_string_fexpr = bool(self.string_stack)
            if tok:
                return [tok, endtok]
            return [endtok]

    def _fexpr_unit(self, mgr: _FormattedStrManager, is_cmd: bool) \
            -> List[Token]:
        """
        Helper for parsing formatted expression in string and command.
        Read a character / escape sequence / start of a formatted
        expression. Return True if we got a formatted expression.
        is_cmd: True if we are in a command, False if we are in a string
        NOTE Caller needs to ensure `self.current_char` is not None.
        """
        peek = self.peek()
        res = []
        if self.current_char == '\\' and peek == '$':
            # special escape in commands
            mgr.add_text('$', self.current_pos)
            self.forward()  # skip "\\"
            self.forward()  # skip "$"
        elif self.current_char == '$' and peek == '{':
            # formatted expression
            tok = mgr.retrieve_text_token(self.current_pos)
            if tok:
                res.append(tok)
            with self.make_token(TokenType.dollar_lbrace) as gettok:
                self.forward()  # skip "$"
                self.bracket_stack.append(_BracketFrame(
                    TokenType.lbrace, self.current_pos,
                    **{("cmd_fexpr" if is_cmd else "str_fexpr"): True}
                ))  # Make sure position points to "{", not "$"
                self.forward()  # skip "{"
            dollar_lbrace = gettok()
            res.append(dollar_lbrace)
            # Use `mgr.last_dollar_lbrace` to track where last "${" is
            # for better error messages.
            mgr.last_dollar_lbrace = dollar_lbrace
            if is_cmd:
                self.in_command_fexpr = True
            else:
                self.in_string_fexpr = True
        else:  # a normal character
            pos = self.current_pos
            mgr.add_text(self._read_escapable_char(), pos)
        return res

    def handle_long_command(self) -> List[Token]:
        """Help read a multi-line /*...*/ command. Return the tokens."""
        mgr = self.inside_command
        assert mgr is not None
        while not (self.current_char == '*' and self.peek() == '/'):
            # check whether we reach end of line
            if self.current_char in ("\n", None):
                # replace "\n" with " " (space)
                mgr.add_text(' ', self.current_pos)
                return []
            tokens = self._fexpr_unit(mgr, is_cmd=True)
            if tokens:
                return tokens
        else:
            tok = mgr.retrieve_text_token(self.current_pos)
            with self.make_token(TokenType.command_end) as gettok:
                self.forward()  # skip "*"
                self.forward()  # skip "/"
            endtok = gettok()
            self.continued_command = False
            self.inside_command = None
            if tok:
                return [tok, endtok]
            return [endtok]

    def handle_command(self) -> List[Token]:
        """Help read a single line command. Return the tokens."""
        mgr = self.inside_command
        assert mgr is not None
        while self.current_char is not None and self.current_char != '\n':
            tokens = self._fexpr_unit(mgr, is_cmd=True)
            if tokens:
                return tokens
        else:
            self.inside_command = None
            tok = mgr.retrieve_text_token(self.current_pos)
            endtok = self.make_zerowidth_token(TokenType.command_end)
            if tok:
                return [tok, endtok]
            return [endtok]

    def handle_interface_path(self) -> Token:
        """Help read an interface path."""
        # Read as long as current char is in FUNCTION_PATH_CHARS. Note
        # that Acacia removes support for unquoted parenthesis
        # characters.
        chars = []
        with self.make_token(TokenType.interface_path) as gettok:
            while (
                self.current_char in FUNCTION_PATH_CHARS
                and self.current_char not in ('(', ')')
            ):
                chars.append(self.current_char)
                self.forward()
        if not chars:
            self.error('interface-path-expected')
        return gettok(value=''.join(chars))
