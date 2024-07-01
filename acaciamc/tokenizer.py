"""Tokenizer (Lexer) for Acacia."""

__all__ = ['TokenType', 'Token', 'Tokenizer']

import enum
import string
from typing import (
    Union, List, TextIO, Tuple, Dict, Optional, NamedTuple, Any, TYPE_CHECKING
)

from acaciamc.constants import COLORS, COLORS_NEW, FUNCTION_PATH_CHARS
from acaciamc.error import *

if TYPE_CHECKING:
    from acaciamc.tools.versionlib import VERSION_T

UNICODE_ESCAPES = {'x': 2, 'u': 4, 'U': 8}
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
    float_ = 'FLOAT'  # value: float
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
    type: TokenType
    lineno: int
    col: int
    value: Any = None

    def __str__(self) -> str:
        v = self.type.value
        if not v.isupper():
            v = repr(v)
        if self.value is not None:
            v += ' (%s)' % self.value
        return v

    def __repr__(self):
        if self.value is None:
            value_str = ''
        else:
            value_str = '(%s)' % (self.value,)
        return '<Token %s%s at %s:%s>' % (
            self.type.name, value_str,
            self.lineno, self.col
        )


class _FormattedStrManager:
    def __init__(self, owner: 'Tokenizer',
                 begin_tok: TokenType, end_tok: TokenType) -> None:
        self.lineno = owner.current_lineno
        self.col = owner.current_col
        self.owner = owner
        self.begin_tok = begin_tok
        self.end_tok = end_tok
        self._texts: List[str] = []
        self._text_ln = 0
        self._text_col = 0
        self._tokens: List[Token] = [
            Token(self.begin_tok, self.lineno, self.col)
        ]

    def _dump_texts(self):
        if self._texts:
            self._tokens.append(Token(
                TokenType.text_body,
                self._text_ln, self._text_col, "".join(self._texts)
            ))
            self._texts.clear()

    def add_text(self, text: str):
        if not self._texts:
            self._text_ln = self.owner.current_lineno
            self._text_col = self.owner.current_col
        self._texts.append(text)

    def add_token(self, token: Token):
        self._dump_texts()
        self._tokens.append(token)

    def get_tokens(self) -> List[Token]:
        res = self._tokens.copy()
        self._tokens.clear()
        return res

    def finish(self):
        self._dump_texts()
        self._tokens.append(self.owner.gen_token(self.end_tok))


class _CommandManager(_FormattedStrManager):
    def __init__(self, owner: 'Tokenizer') -> None:
        super().__init__(owner, TokenType.command_begin, TokenType.command_end)


class _StrLiteralManager(_FormattedStrManager):
    def __init__(self, owner: 'Tokenizer') -> None:
        super().__init__(owner, TokenType.string_begin, TokenType.string_end)


class _BracketFrame(NamedTuple):
    type: TokenType
    pos: Tuple[int, int]
    cmd_fexpr: bool = False
    str_fexpr: bool = False


class Tokenizer:
    def __init__(self, src: TextIO, mc_version: "VERSION_T"):
        """src: source code"""
        self.src = src
        self.mc_version = mc_version
        self.current_char = ''
        self.current_lineno = 0
        self.current_col = 0
        self.position = 0  # string pointer
        self.buffer_tokens: List[Token] = []
        self.bracket_stack: List[_BracketFrame] = []
        self.indent_record: List[int] = [0]
        self.indent_len: int = 1  # always = len(self.indent_record)
        self.has_content = False  # if this logical line produced token
        self.last_line_continued = False
        self.inside_command: Optional[_CommandManager] = None
        self.in_command_fexpr = False
        self.string_stack: List[_StrLiteralManager] = []
        self.in_string_fexpr = False  # in fexpr of the most inner string
        self.continued_command = False
        self.continued_comment = False
        self.continued_comment_pos: Union[None, Tuple[int, int]] = None
        self.last_is_interface = False

    def error(self, err_type: ErrorType, lineno=None, col=None, **kwargs):
        if lineno is None:
            lineno = self.current_lineno
        if col is None:
            col = self.current_col
        err = Error(err_type, **kwargs)
        err.location.linecol = (lineno, col)
        raise err

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

    def is_in_bracket(self) -> bool:
        return bool(self.bracket_stack)

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
                or self.is_in_bracket()):
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
                    self.forward()
                    self.forward()
                    self.continued_comment_pos = (self.current_lineno,
                                                  self.current_col)
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
                    self.enter_string()
                    self.forward()
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
                self.inside_command = _CommandManager(self)
                self.forward()  # skip "/"
                if self.current_char == '*':
                    self.continued_command = True
                    self.forward()  # skip "*"
            elif self.current_char == '"':
                self.forward()  # skip '"'
                self.enter_string()
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
                    res.append(self.gen_token(token_type))
                    self.forward()
                    self.forward()
                    continue
            ## try one-char token
            try:
                token_type = TokenType(self.current_char)
            except ValueError:
                # We've run out of possibilities.
                self.error(ErrorType.INVALID_CHAR, char=self.current_char)
            else:
                if token_type in BRACKETS:
                    self.bracket_stack.append(_BracketFrame(
                        token_type,
                        (self.current_lineno, self.current_col)
                    ))
                elif token_type in RB2LB:
                    if not self.bracket_stack:
                        self.error(ErrorType.UNMATCHED_BRACKET,
                                   char=self.current_char)
                    expect = RB2LB[token_type]
                    got_f = self.bracket_stack.pop()
                    got = got_f.type
                    if got is not expect:
                        self.error(ErrorType.UNMATCHED_BRACKET_PAIR,
                                   open=got.value, close=token_type.value)
                    if got is TokenType.lbrace:
                        if got_f.cmd_fexpr:
                            self.in_command_fexpr = False
                        elif got_f.str_fexpr:
                            self.in_string_fexpr = False
                res.append(self.gen_token(token_type))
                self.forward()
        # Now self.current_char is either '\n', '\\' or None (EOF)
        if (
                # ${} in single line command can't use implicit line continuation.
                (self.in_command_fexpr and not self.continued_command)
                # And so is ${} in string literal.
                or self.in_string_fexpr
        ):
            self.error(ErrorType.UNCLOSED_FEXPR)
        backslash = False
        eof = False
        if res:
            self.has_content = True
        if self.current_char == '\n':
            if self.has_content and not (
                    self.continued_comment or self.continued_command
                    or self.is_in_bracket()
            ):
                res.append(self.handle_logical_newline())
            self.last_line_continued = False
        elif self.current_char is None:
            if self.continued_comment:
                self.error(ErrorType.UNCLOSED_LONG_COMMENT,
                           *self.continued_comment_pos)
            if self.continued_command:
                if self.in_command_fexpr:
                    self.error(ErrorType.UNCLOSED_FEXPR)
                self.error(ErrorType.UNCLOSED_LONG_COMMAND,
                           self.inside_command.lineno,
                           self.inside_command.col)
            if self.is_in_bracket():
                br = self.bracket_stack[-1]
                self.error(ErrorType.UNCLOSED_BRACKET,
                           *br.pos, char=br.type.value)
            if self.has_content:
                res.append(self.handle_logical_newline())
            eof = True
        elif self.current_char == '\\':
            self.forward()  # skip "\\"
            if self.current_char is None:
                self.error(ErrorType.EOF_AFTER_CONTINUATION)
            if self.current_char != '\n':
                self.error(ErrorType.CHAR_AFTER_CONTINUATION)
            backslash = self.last_line_continued = True
        # Count indent: if this physical line is not a continued line,
        # and (this physical line has content or ends with backslash)
        if (res or backslash) and prespaces != -1:
            res[:0] = self.handle_indent(prespaces)
        # Add a fake line to clean up if we reach end of file
        if eof:
            self.current_lineno += 1
            self.current_col = 0
            res.extend(self.handle_indent(0))  # dump DEDENTs
            res.append(self.gen_token(TokenType.end_marker))
        return res

    def gen_token(self, *args, **kwargs):
        """Generate a token at current pos."""
        return Token(
            lineno=self.current_lineno, col=self.current_col,
            *args, **kwargs
        )

    def skip_spaces(self):
        """Skip white spaces."""
        while self.current_char == ' ':
            self.forward()

    def skip_comment(self):
        """Skip a single-line # comment."""
        while self.current_char is not None and self.current_char != '\n':
            self.forward()

    def enter_string(self):
        """Enter a string literal."""
        self.string_stack.append(_StrLiteralManager(self))
        self.in_string_fexpr = False

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

    def handle_logical_newline(self):
        """Generate a logical NEWLINE token and do checks."""
        if self.last_is_interface:
            self.error(ErrorType.INTERFACE_PATH_EXPECTED)
        return self.gen_token(TokenType.new_line)

    def handle_indent(self, spaces: int) -> List[Token]:
        """Generate INDENT and DEDENT."""
        ln = self.current_lineno
        tokens = []
        if spaces > self.indent_record[-1]:
            self.indent_record.append(spaces)
            self.indent_len += 1
            tokens.append(Token(TokenType.indent, lineno=ln, col=0))
        elif spaces in self.indent_record:
            i = self.indent_record.index(spaces)
            dedent_count = self.indent_len - 1 - i
            self.indent_record = self.indent_record[:i + 1]
            self.indent_len -= dedent_count
            tokens.extend(Token(TokenType.dedent, lineno=ln, col=0)
                          for _ in range(dedent_count))
        else:
            self.error(ErrorType.INVALID_DEDENT)
        return tokens

    @staticmethod
    def _isdecimal(char: Union[str, None]):
        return char is not None and char in string.digits

    def handle_number(self):
        """Read an INTEGER or a FLOAT token."""
        res = []
        ln, col = self.current_lineno, self.current_col
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
            return Token(TokenType.float_, value=value, lineno=ln, col=col)
        else:  # integer
            if not res:
                self.error(ErrorType.INTEGER_REQUIRED, base=base)
            value = int(''.join(res), base=base)
            return Token(TokenType.integer, value=value, lineno=ln, col=col)

    def handle_name(self):
        """Read a keyword or an IDENTIFIER token."""
        chars = []
        ln, col = self.current_lineno, self.current_col
        while is_idcontinue(self.current_char):
            chars.append(self.current_char)
            self.forward()
        name = ''.join(chars)
        token_type = KEYWORDS.get(name)
        if token_type is None:  # IDENTIFIER
            return Token(TokenType.identifier, value=name, lineno=ln, col=col)
        # Keyword
        return Token(token_type, lineno=ln, col=col)

    def _font2char(self, word: str) -> Optional[str]:
        if word in COLORS:
            return COLORS[word]
        if word in COLORS_NEW and self.mc_version >= (1, 19, 80):
            return COLORS_NEW[word]
        if word in FONTS:
            return FONTS[word]
        return None

    def _read_escapable_char(self) -> str:
        """Read current char as an escapable one (in string or command)
        and skip the read char(s). Return the handled char(s).
        """
        first = self.current_char
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
            start_ln, start_col = self.current_lineno, self.current_col
            res: List[str] = []
            cur_spec: List[str] = []
            self.forward()  # skip '('
            while True:
                if self.current_char is None or self.current_char == '\n':
                    self.error(ErrorType.UNCLOSED_FONT,
                               lineno=start_ln, col=start_col)
                if self.current_char in (',', ')'):
                    font = ''.join(cur_spec).strip()
                    cur_spec.clear()
                    ch = self._font2char(font)
                    if ch is None:
                        self.error(ErrorType.INVALID_FONT, font=font,
                                   lineno=start_ln, col=start_col)
                    res.append(f"\xA7{ch}")
                    if self.current_char == ')':
                        break
                else:
                    cur_spec.append(self.current_char)
                self.forward()
            self.forward()  # skip ')'
            return ''.join(res)
        ## NOTE '\n' should be passed directly to MC
        ## because MC use '\n' escape too
        elif second in UNICODE_ESCAPES:  # unicode number
            def _err():
                self.error(ErrorType.INVALID_UNICODE_ESCAPE,
                           escape_char=second)

            self.forward()  # skip '\\'
            code = []
            length = UNICODE_ESCAPES[second]
            for _ in range(length):
                if self.current_char not in string.hexdigits:
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
                self.error(ErrorType.UNCLOSED_QUOTE,
                           lineno=mgr.lineno, col=mgr.col)
            if self.current_char == '\\' and self.peek() == '"':
                # special escape in strings
                mgr.add_text('"')
                self.forward()
                self.forward()
                continue
            if self._fexpr_unit(mgr, is_cmd=False):
                break
        else:
            self.forward()  # skip last '"'
            mgr.finish()
            self.string_stack.pop()
            self.in_string_fexpr = bool(self.string_stack)
        return mgr.get_tokens()

    def _fexpr_unit(self, mgr: _FormattedStrManager, is_cmd: bool) -> bool:
        """
        Helper for parsing formatted expression in string and command.
        Read a character / escape sequence / start of a formatted
        expression. Return True if we got a formatted expression.
        is_cmd: True if we are in a command, False if we are in a string
        """
        peek = self.peek()
        do_break = False
        if self.current_char == '\\' and peek == '$':
            # special escape in commands
            mgr.add_text('$')
            self.forward()  # skip "\\"
            self.forward()  # skip "$"
        elif self.current_char == '$' and peek == '{':
            # formatted expression
            mgr.add_token(self.gen_token(TokenType.dollar_lbrace))
            self.forward()  # skip "$"
            self.bracket_stack.append(_BracketFrame(
                TokenType.lbrace,
                (self.current_lineno, self.current_col),
                **{("cmd_fexpr" if is_cmd else "str_fexpr"): True}
            ))  # Make sure position points to "{", not "$"
            self.forward()  # skip "{"
            if is_cmd:
                self.in_command_fexpr = True
            else:
                self.in_string_fexpr = True
            do_break = True
        else:  # a normal character
            mgr.add_text(self._read_escapable_char())
        return do_break

    def handle_long_command(self) -> List[Token]:
        """Help read a multi-line /*...*/ command. Return the tokens."""
        mgr = self.inside_command
        while not (self.current_char == '*' and self.peek() == '/'):
            # check whether we reach end of line
            if self.current_char in ("\n", None):
                # replace "\n" with " " (space)
                mgr.add_text(' ')
                break
            if self._fexpr_unit(mgr, is_cmd=True):
                break
        else:
            mgr.finish()
            self.forward()  # skip "*"
            self.forward()  # skip "/"
            self.continued_command = False
            self.inside_command = None
        return mgr.get_tokens()

    def handle_command(self) -> List[Token]:
        """Help read a single line command. Return the tokens."""
        mgr = self.inside_command
        while self.current_char is not None and self.current_char != '\n':
            if self._fexpr_unit(mgr, is_cmd=True):
                break
        else:
            mgr.finish()
            self.inside_command = None
        return mgr.get_tokens()

    def handle_interface_path(self) -> Token:
        """Help read an interface path."""
        ln, col = self.current_lineno, self.current_col
        # Read as long as current char is in FUNCTION_PATH_CHARS. Note
        # that Acacia removes support for parenthesis characters.
        chars = []
        while (
                self.current_char in FUNCTION_PATH_CHARS
                and self.current_char not in ('(', ')')
        ):
            chars.append(self.current_char)
            self.forward()
        if not chars:
            self.error(ErrorType.INTERFACE_PATH_EXPECTED)
        path = ''.join(chars)
        return Token(TokenType.interface_path, lineno=ln, col=col, value=path)
