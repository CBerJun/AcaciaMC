"""Tokenizer (Lexer) for Acacia."""

__all__  = ['TokenType', 'Token', 'Tokenizer']

from typing import Union, List, TextIO, Tuple, Dict, Optional
import enum

from acaciamc.error import *
from acaciamc.constants import COLORS, COLORS_NEW, Config

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
    1. If value is one character (len==1), then a single character
    token is registered. (e.g. '=')
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
    bar = '|'
    colon = ':'
    comma = ','
    end_marker = 'END_MARKER'  # end of file
    # command
    command_begin = 'COMMAND_BEGIN'
    command_string = 'COMMAND_STRING'  # value: str
    dollar_lbrace = '${'
    command_end = 'COMMAND_END'
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
    # expressions
    ## literal
    integer = 'INTEGER'  # value: int
    string = 'STRING'  # value: str
    float_ = 'FLOAT'  # value: float
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

class Token:
    def __init__(self, token_type: TokenType,
                 lineno: int, col: int, value=None):
        # lineno & col position where token starts
        self.lineno = lineno
        self.col = col
        self.type = token_type
        self.value = value

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

class _CommandManager:
    def __init__(self, owner: 'Tokenizer') -> None:
        self.lineno = owner.current_lineno
        self.col = owner.current_col
        self.owner = owner
        self._texts = ""
        self._text_ln = 0
        self._text_col = 0
        self._tokens: List[Token] = [
            Token(TokenType.command_begin, self.lineno, self.col)
        ]

    def _dump_texts(self):
        if self._texts:
            self._tokens.append(Token(
                TokenType.command_string,
                self._text_ln, self._text_col, self._texts
            ))
            self._texts = ""

    def add_text(self, text: str):
        if not self._texts:
            self._text_ln = self.owner.current_lineno
            self._text_col = self.owner.current_col
        self._texts += text

    def add_token(self, token: Token):
        self._dump_texts()
        self._tokens.append(token)

    def get_tokens(self) -> List[Token]:
        res = self._tokens.copy()
        self._tokens.clear()
        return res

    def finish(self):
        self._dump_texts()
        self._tokens.append(Token(
            TokenType.command_end, self.owner.current_lineno,
            self.owner.current_col
        ))

class Tokenizer:
    def __init__(self, src: TextIO):
        """src: source code"""
        self.src = src
        self.current_char = ''
        self.current_lineno = 0
        self.current_col = 0
        self.position = 0  # string pointer
        self.buffer_tokens: List[Token] = []
        self.parens = 0
        self.brackets = 0
        self.braces = 0
        self.dollar_lbrace = False
        self.prespaces = 0
        self.indent_record: List[int] = [0]
        self.indent_len: int = 1  # always = len(self.indent_record)
        self.last_token_newline = True  # whether last token is new_line
        self.last_line_continued = False
        self.inside_command: Optional[_CommandManager] = None
        self.continued_command = False
        self.continued_comment = False
        self.continued_comment_pos: Union[None, Tuple[int, int]] = None

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
        return self.parens > 0 or self.brackets > 0 or self.braces > 0

    def parse_line(self) -> List[Token]:
        """Parse a line."""
        self.current_line = self.src.readline()
        self.line_len = len(self.current_line)
        self.current_lineno += 1
        self.current_col = 0
        self.position = 0
        res: List[Token] = []
        self.forward()
        def _gen_token(*args, **kwargs):
            """Generate a token on current pos."""
            return Token(
                lineno=self.current_lineno, col=self.current_col,
                *args, **kwargs
            )
        def _gen_and_forward(token_type: TokenType, forward_times=1):
            """Generate a token of the specified type
            NOTE by generating token first, we make sure the position is
            correctly at the start of token (`self.forward` changes
            `self.lineno` and `self.col`).
            """
            token = _gen_token(token_type)
            for _ in range(forward_times):
                self.forward()
            return token
        # read indent
        if not (self.continued_command
                or self.continued_comment
                or self.last_line_continued
                or self.is_in_bracket()):
            # Continued lines' indent should be the same as the first
            # line.
            self.prespaces = 0
            while self.current_char == ' ':
                self.prespaces += 1
                self.forward()
        # continued token
        else:
            if self.continued_comment:
                self.handle_long_comment()
        while True:
            if self.inside_command and not self.dollar_lbrace:
                if self.continued_command:
                    res.extend(self.handle_long_command())
                    assert self.continued_command or not self.dollar_lbrace
                    # If dollar lbrace is not closed, then the long
                    # command should not have ended. Instead the
                    # tokenizer would keep tokenizing as normal.
                    # e.g. `/* ${ */` results in unexpected token '*'.
                else:
                    res.extend(self.handle_command())
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
            ## special tokens
            if self.current_char.isdecimal():
                res.append(self.handle_number())
            elif self.current_char.isalpha() or self.current_char == '_':
                res.append(self.handle_name())
            elif self.current_char == '/' and not res:
                # Only read when "/" is first character of this line
                self.forward()  # skip "/"
                self.inside_command = _CommandManager(self)
                if self.current_char == '*':
                    self.continued_command = True
                    self.forward()  # skip "*"
            elif self.current_char == '"':
                res.append(self.handle_string())
            else:  ## 2-char token
                peek = self.peek()
                for pattern in (
                    '==', '>=', '<=', '!=', '->',
                    '+=', '-=', '*=', '/=', '%=', ':='
                ):
                    if self.current_char == pattern[0] and peek == pattern[1]:
                        res.append(_gen_and_forward(TokenType(pattern), 2))
                        break
                else:  ## 1-char token
                    try:
                        token_type = TokenType(self.current_char)
                    except ValueError:
                        ## does not match any tokens
                        self.error(ErrorType.INVALID_CHAR,
                                   char=self.current_char)
                    else:
                        if token_type is TokenType.lparen:
                            self.parens += 1
                        elif token_type is TokenType.lbracket:
                            self.brackets += 1
                        elif token_type is TokenType.lbrace:
                            self.braces += 1
                        elif token_type is TokenType.rparen:
                            self.parens -= 1
                            if self.parens < 0:
                                self.error(ErrorType.UNMATCHED_PAREN)
                        elif token_type is TokenType.rbracket:
                            self.brackets -= 1
                            if self.brackets < 0:
                                self.error(ErrorType.UNMATCHED_BRACKET)
                        elif token_type is TokenType.rbrace:
                            if self.dollar_lbrace:
                                self.dollar_lbrace = False
                            else:
                                self.braces -= 1
                                if self.braces < 0:
                                    self.error(ErrorType.UNMATCHED_BRACE)
                        res.append(_gen_and_forward(token_type, 1))
        # Now self.current_char is either '\n', '\\' or None (EOF)
        if self.dollar_lbrace and not self.continued_command:
            # Single line command can't use implicit line continuation.
            self.error(ErrorType.UNCLOSED_FEXPR)
        has_content = bool(res)
        if self.current_char == '\n':
            if has_content:
                if not (
                    self.continued_comment or self.continued_command
                    or self.is_in_bracket()
                ):
                    res.append(_gen_token(TokenType.new_line))
                if self.last_token_newline:
                    res = self.handle_indent(self.prespaces) + res
            self.last_line_continued = False
        elif self.current_char is None:
            if self.continued_comment:
                self.error(ErrorType.UNCLOSED_LONG_COMMENT,
                           *self.continued_comment_pos)
            if self.continued_command:
                self.error(ErrorType.UNCLOSED_LONG_COMMAND,
                           self.inside_command.lineno,
                           self.inside_command.col)
            if self.last_line_continued:
                self.error(ErrorType.EOF_AFTER_CONTINUATION)
            if self.is_in_bracket():
                self.error(ErrorType.UNCLOSED_BRACKET)
            if has_content:
                res.append(_gen_token(TokenType.new_line))
                res = self.handle_indent(self.prespaces) + res
            # Create a fake line for cleanup
            self.current_lineno += 1
            self.current_col = 0
            res.extend(self.handle_indent(0))  # dump DEDENTs
            res.append(_gen_token(TokenType.end_marker))
        elif self.current_char == '\\':
            self.forward()  # skip "\\"
            while self.current_char not in ('\n', None):
                if not self.current_char.isspace():
                    self.error(ErrorType.CHAR_AFTER_CONTINUATION)
                self.forward()
            if has_content and self.last_token_newline:
                res = self.handle_indent(self.prespaces) + res
            self.last_line_continued = True
        if has_content:
            self.last_token_newline = res[-1].type is TokenType.new_line
        return res

    def skip_spaces(self):
        """Skip white spaces."""
        while self.current_char == ' ':
            self.forward()

    def skip_comment(self):
        """Skip a single-line # comment."""
        while self.current_char is not None and self.current_char != '\n':
            self.forward()

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
            self.indent_record = self.indent_record[:i+1]
            self.indent_len -= dedent_count
            tokens.extend(Token(TokenType.dedent, lineno=ln, col=0)
                          for _ in range(dedent_count))
        else:
            self.error(ErrorType.INVALID_DEDENT)
        return tokens

    @staticmethod
    def _isdecimal(char: Union[str, None]):
        return char is not None and char.isdecimal()

    def handle_number(self):
        """Read an INTEGER or a FLOAT token."""
        res = ''
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
            res += self.current_char
            self.forward()
        ## convert string to number
        if (self.current_char == "."
            and base == 10
            and self._isdecimal(self.peek())
        ):  # float
            self.forward()
            res += "."
            while self._isdecimal(self.current_char):
                res += self.current_char
                self.forward()
            value = float(res)
            return Token(TokenType.float_, value=value, lineno=ln, col=col)
        else:  # integer
            if not res:
                self.error(ErrorType.INTEGER_REQUIRED, base=base)
            value = int(res, base=base)
            return Token(TokenType.integer, value=value, lineno=ln, col=col)

    def handle_name(self):
        """Read a keyword or an IDENTIFIER token."""
        name = ''
        ln, col = self.current_lineno, self.current_col
        while ((self.current_char is not None)
               and (self.current_char.isalnum() or self.current_char == '_')):
            name += self.current_char
            self.forward()
        token_type = KEYWORDS.get(name)
        if token_type is None:  # IDENTIFIER
            return Token(TokenType.identifier, value=name, lineno=ln, col=col)
        # Keyword
        return Token(token_type, lineno=ln, col=col)

    def _read_escapable_char(self) -> str:
        """Read current char as an escapable one (in string or command)
        and skip the read char(s). Return the handled char(s).
        """
        first = self.current_char
        self.forward()
        second = self.current_char
        # not escapable
        if first != '\\':
            return first
        # escapable
        if second == '\\':  # backslash itself
            self.forward()  # skip second backslash
            return second
        elif second == '#':  # font
            self.forward()  # skip '#'
            third = self.current_char
            start_ln, start_col = self.current_lineno, self.current_col
            if third == '(':
                res = ''
                spec = ''
                self.forward()  # skip '('
                while self.current_char != ')':
                    if self.current_char is None or self.current_char == '\n':
                        self.error(ErrorType.UNCLOSED_FONT,
                                   lineno=start_ln, col=start_col)
                    spec += self.current_char
                    self.forward()
                self.forward()  # skip ')'
                for word in spec.split(","):
                    word = word.strip()
                    res += '\xA7'
                    if word in COLORS:
                        res += COLORS[word]
                    elif (word in COLORS_NEW
                          and Config.mc_version >= (1, 19, 80)):
                        res += COLORS_NEW[word]
                    elif word in FONTS:
                        res += FONTS[word]
                    else:
                        self.error(ErrorType.INVALID_FONT, font=word,
                                   lineno=start_ln, col=start_col)
            else:
                res = '\xA7'
            return res
        ## NOTE '\n' should be passed directly to MC
        ## because MC use '\n' escape too
        elif second in 'xuU':  # unicode number
            def _err():
                self.error(ErrorType.INVALID_UNICODE_ESCAPE,
                           escape_char=second)
            self.forward()  # skip '\\'
            code = ''
            length = {'x': 2, 'u': 4, 'U': 8}[second]
            VALID_CHARS = tuple('0123456789ABCDEFabcdef')
            for _ in range(length):
                if self.current_char not in VALID_CHARS:
                    _err()
                code += self.current_char
                self.forward()
            # get code
            try:
                unicode = int(code, base=16)
            except ValueError:
                _err()
            if unicode >= 0x110000:
                _err()
            return chr(unicode)
        # when escape can't be recognized, just return "\\"
        # and the `second` char will be handled later
        return first  # (here first == '\\')

    def handle_string(self):
        """Read a STRING token."""
        ln, col = self.current_lineno, self.current_col
        res = ''
        self.forward()  # skip first '"'
        while self.current_char != '"':
            # check None and \n
            if (self.current_char is None) or (self.current_char == '\n'):
                self.error(ErrorType.UNCLOSED_QUOTE, lineno=ln, col=col)
            if self.current_char == '\\' and self.peek() == '"':
                # special escape in strings
                res += '"'
                self.forward()
                self.forward()
                continue
            res += self._read_escapable_char()
        self.forward()  # skip last '"'
        return Token(TokenType.string, lineno=ln, col=col, value=res)

    def _command_unit(self) -> bool:
        """
        Helper for parsing commands.
        Read a character / escape sequence / start of a formatted
        expression. Return True if we got a formatted expression.
        """
        mgr = self.inside_command
        peek = self.peek()
        do_break = False
        if self.current_char == '\\' and peek == '$':
            # special escape in commands
            mgr.add_text('$')
            self.forward()  # skip "\\"
            self.forward()  # skip "$"
        elif self.current_char == '$' and peek == '{':
            # formatted expression
            mgr.add_token(Token(
                TokenType.dollar_lbrace, lineno=self.current_lineno,
                col=self.current_col
            ))
            self.dollar_lbrace = True
            self.forward()
            self.forward()  # skip "${"
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
            if self._command_unit():
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
            if self._command_unit():
                break
        else:
            mgr.finish()
            self.inside_command = None
        return mgr.get_tokens()
