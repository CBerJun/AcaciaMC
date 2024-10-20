"""Tokenizer (Lexer) for Acacia."""

from typing import (
    Union, List, TextIO, Tuple, Dict, Optional, NamedTuple, Any, Callable,
    Generator, Mapping, Deque, TYPE_CHECKING
)
from contextlib import contextmanager
from string import ascii_letters, digits, hexdigits
from collections import deque
from itertools import repeat
import enum

from acaciamc.reader import LineCol, LineColRange
from acaciamc.utils import is_int32
from acaciamc.utils.str_template import STInt, STStr, STArgument
from acaciamc.diagnostic import Diagnostic, DiagnosticError

if TYPE_CHECKING:
    from acaciamc.reader import FileEntry
    from acaciamc.diagnostic import DiagnosticsManager

UNICODE_ESCAPES = {'x': 2, 'u': 4, 'U': 8}
INT_LITERAL_BASES = {'x': 16, 'b': 2, 'o': 8}
# I feel like defining this ourselves (instead of `string.hexdigits`) is
# more straight forward since we are going to slice this:
CAPITAL_HEX_DIGITS = '0123456789ABCDEF'
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
    Value convention:
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
    return_ = 'return'
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
    return is_idstart(c) or c in digits

class Token(NamedTuple):
    """
    A token with `type` type that ranges from before the character
    pointed by `pos1` to before the character pointed by `pos2`. The
    payload `value` defaults to None. Line and column numbers are
    1-indexed (just like all other places).
    """

    type: TokenType
    pos1: LineCol
    pos2: LineCol
    value: Any = None

    @property
    def range(self) -> LineColRange:
        return (self.pos1, self.pos2)

    def __repr__(self) -> str:
        if self.value is None:
            value_str = ''
        else:
            value_str = f'({self.value!r})'
        return '<Token %s%s at %d:%d-%d:%d>' % (
            self.type.name, value_str,
            *self.pos1, *self.pos2
        )

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
        self.text_pos: Optional[LineCol] = None
        # The `start_token` is not used by us, but `Tokenizer` uses it
        # to track where the we start in source.
        self.start_token = start_token
        # This is not used by us, but by `Tokenizer`:
        self.last_dollar_lbrace: Optional[Token] = None

    def add_text(self, text: str, pos: LineCol) -> None:
        if self.text_pos is None:
            self.text_pos = pos
        self.texts.append(text)

    def retrieve_text_token(self, pos: LineCol) -> Optional[Token]:
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
    pos: LineCol
    cmd_fexpr: bool = False
    str_fexpr: bool = False

def source_range_from_pos(pos: LineCol, length: int) -> LineColRange:
    """
    Get a `LineColRange` that starts at `pos` and has length `length`.
    Note that this does not take care of line breaks.
    """
    return (pos, (pos[0], pos[1] + length))

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
        self.buffer_tokens: Deque[Token] = deque()
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
        self.continued_comment_pos: Optional[LineCol] = None
        # Indicate if the last token was INTERFACE:
        self.last_is_interface = False

    @property
    def current_pos(self) -> LineCol:
        return self.current_lineno, self.current_col

    def error(self, diag_id: str, pos: Optional[LineCol] = None,
              args: Mapping[str, STArgument] = {}):
        """Raise an ERROR diagnostic on a specific location in source."""
        if pos is None:
            pos = self.current_pos
        self.error_range(diag_id, (pos, pos), args)

    def error_range(
        self, diag_id: str, r: LineColRange,
        args: Mapping[str, STArgument] = {}
    ):
        """Raise an ERROR diagnostic on a range in source."""
        raise DiagnosticError(Diagnostic(
            diag_id, self.file_entry, r, args=args
        ))

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
        return self.buffer_tokens.popleft()

    def parse_line(self) -> Deque[Token]:
        """Parse a line."""
        self.current_line = self.src.readline()
        self.line_len = len(self.current_line)
        self.current_lineno += 1
        self.current_col = 0
        self.position = 0
        res: Deque[Token] = deque()
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
            if self.current_char in digits:
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
                    'invalid-char', source_range_from_pos(self.current_pos, 1),
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
                            source_range_from_pos(self.current_pos, 1),
                            args={'char': STStr(self.current_char)}
                        )
                    expect = RB2LB[token_type]
                    got_f = self.bracket_stack.pop()
                    got = got_f.type
                    if got is not expect:
                        self.error_range(
                            'unmatched-bracket-pair',
                            source_range_from_pos(self.current_pos, 1),
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
            # Throw
            self.error_range('unclosed-fexpr', mgr.last_dollar_lbrace.range)
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
                self.error_range(
                    'unclosed-long-comment',
                    # 2 is the length of "#*".
                    source_range_from_pos(self.continued_comment_pos, 2)
                )
            if self.continued_command:
                assert self.inside_command
                if self.in_command_fexpr:
                    command_dl = self.inside_command.last_dollar_lbrace
                    assert command_dl is not None
                    self.error_range('unclosed-fexpr', command_dl.range)
                self.error_range('unclosed-long-command',
                                 self.inside_command.start_token.range)
            if self.bracket_stack:
                br = self.bracket_stack[-1]
                # Assume that all brackets are made of just 1 character
                src_range = source_range_from_pos(br.pos, 1)
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
                                 source_range_from_pos(self.current_pos, 1))
            backslash = self.last_line_continued = True
        # Count indent: if this physical line is not a continued line,
        # and (this physical line has content or ends with backslash)
        if (res or backslash) and prespaces != -1:
            token, cnt = self.handle_indent(
                prespaces, begin_col=1,
                # Based on the fact that only spaces are allowed for
                # indentations:
                end_col=prespaces+1
            )
            # We don't need to worry that `extendleft` will reverse the
            # tokens because all tokens are the same!
            res.extendleft(repeat(token, cnt))
        # Now clean up if we reach end of file; this is delayed to be
        # done here because we still want the indent to be emitted
        # first.
        if eof:
            # Dump DEDENTs and emit END_MARKER
            token, cnt = self.handle_indent(
                0, begin_col=self.current_col, end_col=self.current_col
            )
            res.extend(repeat(token, cnt))
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
            -> Tuple[Token, int]:
        """
        Generate INDENT and DEDENT. Return a (token, count) tuple, which
        indicates that *count* duplicates of *token*s should be emitted.
        Usually INDENTs and DEDENTs appear in beginning of line, with
        beginning column number 1, but when dumping DEDENTs at end of
        file, the `begin_col` could be different.
        """
        ln = self.current_lineno
        if spaces > self.indent_record[-1]:
            self.indent_record.append(spaces)
            return Token(TokenType.indent, (ln, begin_col), (ln, end_col)), 1
        try:
            i = self.indent_record.index(spaces)
        except ValueError:
            self.error('invalid-dedent', (ln, begin_col))
        dedent_count = len(self.indent_record) - 1 - i
        del self.indent_record[i + 1:]
        return (Token(TokenType.dedent, (ln, end_col), (ln, end_col)),
                dedent_count)

    @staticmethod
    def _isdecimal(char: Union[str, None]):
        return char is not None and char in digits

    def _handle_integer(self, base: int) -> str:
        """
        Helper for `_handle_number`. Reads an integer of given `base`.
        Return the original source text.
        """
        # Read as long as the character is an identifier character,
        # This makes sure that things like "0a" are not accepted,
        # instead of being tokenized as "0" then an identifier "a".
        valid_chars = CAPITAL_HEX_DIGITS[:base]
        res: List[str] = []
        while (self.current_char is not None
               and is_idcontinue(self.current_char)):
            if self.current_char.upper() not in valid_chars:
                self.error_range(
                    "invalid-number-char",
                    source_range_from_pos(self.current_pos, 1),
                    args={"char": STStr(self.current_char),
                          "base": STInt(base)}
                )
            res.append(self.current_char)
            self.forward()
        return ''.join(res)

    def _handle_number(self) -> Tuple[TokenType, Union[int, float]]:
        """Helper for `handle_number`. Reads a number."""
        # Decide base and check leading zero in decimal numbers
        base = 10
        if self.current_char == '0':
            peek = self.peek()
            if peek is None:
                # "0" at end of file
                self.forward()
                return TokenType.integer, 0
            maybe_base = INT_LITERAL_BASES.get(peek.lower())
            if maybe_base is not None:
                # Successfully read "0x", "0b" or "0o"
                base = maybe_base
                # Skip these two characters
                self.forward()
                self.forward()
        # Read an integer first
        part1 = self._handle_integer(base)
        # Make sure the integer is not empty (e.g. "0x some_more_text")
        if not part1:
            self.error('integer-expected', args={'base': STInt(base)})
        # Check if this is a float
        if (
            self.current_char == "." and base == 10
            and self._isdecimal(self.peek())
        ):
            self.forward()  # skip '.'
            part2 = self._handle_integer(base)
            return TokenType.float, float(f"{part1}.{part2}")
        # Not float -- integer then
        return TokenType.integer, int(part1, base=base)

    def handle_number(self):
        """Read an INTEGER or a FLOAT token."""
        with self.make_token() as gettok:
            tok_type, value = self._handle_number()
        token = gettok(tok_type, value)
        # Check integer overflow
        if tok_type is TokenType.integer:
            assert isinstance(value, int)
            if not is_int32(value):
                self.error_range("integer-literal-overflow", token.range)
        return token

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
        Reads a character and handle escapes if that character is a
        backslash. If the escape cannot be recognized, an ERROR
        diagnostic is issued.
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
        if second in ('\\', '"'):
            self.forward()  # skip the second character
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
                    src_range = source_range_from_pos(
                        (lineno, beginning_col), 3  # len("\\#(") == 3
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
                        # A diagnostic occurred ('new-font' or
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
                            src_range = (
                                (lineno, cur_col + nlspaces),
                                (lineno, self.current_col - nrspaces)
                            )
                        else:
                            src_range = ((lineno, cur_col), (lineno, cur_col))
                    if diag_id == 'invalid-font':
                        self.error_range(
                            diag_id, src_range,
                            args={'font': STStr(font)}
                        )
                    elif diag_id is not None:
                        assert diag_id == 'new-font'
                        self.diagnostic_manager.push_diagnostic(
                            Diagnostic(
                                diag_id, self.file_entry, src_range,
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
        elif second == "n":
            self.forward()  # skip 'n'
            return '\n'
        elif second in UNICODE_ESCAPES:  # unicode number
            self.forward()  # skip UNICODE_ESCAPES character
            code = []
            length = UNICODE_ESCAPES[second]
            unicode_start_col = self.current_col
            for _ in range(length):
                if (
                    self.current_char is None
                    or self.current_char not in hexdigits
                ):
                    self.error_range(
                        'incomplete-unicode-escape',
                        # len('\\x') == len('\\u') == len('\\U') == 2
                        source_range_from_pos((lineno, beginning_col), 2),
                        args={'char': STStr(second)}
                    )
                code.append(self.current_char)
                self.forward()
            code_str = ''.join(code)
            unicode = int(code_str, base=16)
            if unicode >= 0x110000:
                self.error_range(
                    'invalid-unicode-code-point',
                    ((lineno, unicode_start_col), self.current_pos),
                    args={'code': STStr(code_str)}
                )
            return chr(unicode)
        # The escape cannot be recognized
        src_loc = (lineno, beginning_col)
        # Treat End of File specially
        if second is None:
            self.error_range("incomplete-escape",
                             source_range_from_pos(src_loc, 1))
        else:
            self.error_range(
                # 2 is length of '\\' plus the second character
                "invalid-escape", source_range_from_pos(src_loc, 2),
                args={"character": STStr(second)}
            )
        assert False

    def handle_string(self) -> List[Token]:
        """Help read a string literal."""
        mgr = self.string_stack[-1]
        while self.current_char != '"':
            # check None and \n
            if (self.current_char is None) or (self.current_char == '\n'):
                self.error_range('unclosed-quote', mgr.start_token.range)
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
