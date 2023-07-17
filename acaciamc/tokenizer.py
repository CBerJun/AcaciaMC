"""Tokenizer (Lexer) for Acacia."""

__all__  = ['TokenType', 'Token', 'Tokenizer', 'StringMode']

from typing import Union
import enum

from acaciamc.error import *

class TokenType(enum.Enum):
    # block
    lparen = '('
    rparen = ')'
    bar = '|'
    colon = ':'
    comma = ','
    line_begin = 'LINE_BEGIN'  # value:int = indent space counts
    end_marker = 'END_MARKER'  # end of file
    # statement
    command = 'COMMAND'
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
    # expressions
    ## literal
    integer = 'INTEGER'  # value:int = this integer
    string = 'STRING'
    # string value: list[tuple(StringMode, str)]
    # Every tuple in list means a part of string, where mode can be:
    #  text: Normal text
    #  expression: An formatted expression (e.g. "Value: ${expr}")
    float_ = 'FLOAT'  # value:float = this float
    ## id
    identifier = 'IDENTIFIER'  # value:str = this id
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
    false = 'False'  # must at end of keyword part

KEYWORDS = {}
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

    def __str__(self):
        if self.value is None:
            value_str = ''
        else:
            value_str = '(%s)' % (self.value,)
        return '<Token %s%s at %s:%s>' % (
            self.type.name, value_str,
            self.lineno, self.col
        )
    __repr__ = __str__

class StringMode(enum.Enum):
    text = 0
    expression = 1

class CommandToken(Token):
    """A command token, which needs formatted ${expressions}"""
    def __init__(self, lineno, col):
        super().__init__(TokenType.command, lineno, col, value=[])
        self._texts = ''

    def _dump_text(self):
        """Dump stacked _texts into a tuple (StringMode.text, ...)"""
        if self._texts:
            self.value.append((StringMode.text, self._texts))
            self._texts = ''

    def add_text(self, text: str):
        """Add text to command content"""
        self._texts += text

    def add_expression(self, tokenizer: "Tokenizer"):
        """Add a formatted expression to command content
        tokenizer: `Tokenizer` that tokenize the expression"""
        # XXX adding an expression to command now requires creating a new
        # Tokenizer for each expressions, which can be optimized.
        ## first empty _texts
        self._dump_text()
        ## then add expression
        self.value.append((StringMode.expression, tokenizer))

    def command_end(self):
        """Declare that the command has ended and there will not be
        any contents added.
        """
        self._dump_text()

class Tokenizer:
    def __init__(self, src: str):
        """src: source code"""
        self.src = src
        self.current_char = ''
        self.current_lineno = 1
        self.current_col = 0
        self.position = 0  # string pointer
        self.last_token = None  # the last token we've read
        self.SRC_LENGTH = len(self.src)
        # written_line_begin: whether we have written `line_begin`
        # for current line. When a '\n' is read, this is set to False
        self.written_line_begin = False

        self.forward()

    def error(self, err_type: ErrorType, lineno=None, col=None, **kwargs):
        if lineno is None:
            lineno = self.current_lineno
        if col is None:
            col = self.current_col
        err = Error(err_type, **kwargs)
        err.set_location(lineno, col)
        raise err

    def forward(self):
        """Read next char and push pointer."""
        if self.position >= self.SRC_LENGTH:
            self.current_char = None
        else:
            self.current_char = self.src[self.position]
        self.position += 1
        self.current_col += 1
        if self.current_char == '\n':
            self.current_lineno += 1
            self.current_col = 0
            self.written_line_begin = False

    def peek(self, offset=0):
        """Peek the following char without pushing pointer."""
        pos = self.position + offset
        if pos < self.SRC_LENGTH:
            return self.src[pos]
        return None

    def get_next_token(self):
        """Get the next token."""
        self.last_token = self._next_token()
        self._handle_line_continuation()
        return self.last_token

    def _handle_line_continuation(self):
        """Handle line continuation: if current_char is backslash,
        connect this line to next line
        """
        self.skip_spaces()
        if self.current_char == '\\':
            self.forward()  # skip the '\\' itself
            while self.current_char != '\n' and self.current_char is not None:
                if not self.current_char.isspace():
                    self.error(ErrorType.CHAR_AFTER_CONTINUATION)
                self.forward()
            self.forward()  # skip '\n'
            # We don't generate the next `line_begin` token
            # to implement line continuation
            self.written_line_begin = True

    def _next_token(self):
        """Calculate the next token.
        NOTE do not call this directly
        """
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
        # skip
        flag = True
        while flag:
            if self.current_char == ' ':
                self.skip_spaces()
            elif self.current_char == '#':
                if self.peek() == '*':
                    self.skip_long_comment()
                else:
                    self.skip_comment()
            else:
                flag = False
        # check EOF
        peek = self.peek()
        if self.current_char is None:
            return _gen_token(TokenType.end_marker)
        # start
        ## special tokens
        if not self.written_line_begin:
            self.written_line_begin = True
            return self.handle_line_begin()
        if self.current_char.isdecimal():
            return self.handle_number()
        elif self.current_char.isalpha() or self.current_char == '_':
            return self.handle_name()
        elif self.current_char == '/':
            if peek == '*':
                return self.handle_long_command()
            elif self.last_token.type is TokenType.line_begin:
                # a '/' at the beginning of a line is command
                return self.handle_command()
        elif self.current_char == '"':
            return self.handle_string()
        ## 2-char token
        for pattern in (
            '==', '>=', '<=', '!=', '->',
            '+=', '-=', '*=', '/=', '%='
        ):
            if self.current_char == pattern[0] and peek == pattern[1]:
                return _gen_and_forward(TokenType(pattern), 2)
        ## finally check single char
        try:
            token_type = TokenType(self.current_char)
        except ValueError:
            ## does not match any tokens
            self.error(ErrorType.INVALID_CHAR, char=self.current_char)
        else:
            return _gen_and_forward(token_type, 1)

    def skip_spaces(self):
        """Skip white spaces."""
        while self.current_char == ' ':
            self.forward()

    def skip_comment(self):
        """Skip a single-line # comment."""
        while self.current_char is not None and self.current_char != '\n':
            self.forward()

    def skip_long_comment(self):
        """Skip a multi-line #*...*# comment."""
        ln, col = self.current_lineno, self.current_col
        # skip "#*" in case "*" is used both by "#*" and "*#" (like "#*#")
        self.forward()
        self.forward()
        # we want to leave current_char on next char after "#",
        # so use previous_char
        previous_char = ''
        while not (previous_char == '*' and self.current_char == '#'):
            if self.current_char is None:
                self.error(ErrorType.UNCLOSED_LONG_COMMENT, ln, col)
            previous_char = self.current_char
            self.forward()
        self.forward()  # skip char "#"

    def handle_line_begin(self):
        """Read a LINE_BEGIN token."""
        count = 0
        ln = self.current_lineno
        if self.current_char == '\n':  # remove \n (may not exists)
            self.forward()
        while self.current_char == ' ':
            count += 1
            self.forward()
        return Token(TokenType.line_begin, value=count, lineno=ln, col=0)

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
                continue
            res += self._read_escapable_char()
        self.forward()  # skip last '"'
        return Token(TokenType.string, lineno=ln, col=col, value=res)

    # following 2 methods handle commands, which are very similar to
    # method `skip_comment` and `skip_long_comment` above

    def _command_unit(self, result_token: CommandToken):
        """Used by method `handle_command` and `handle_long_command`
        read a unit in command (a normal char, \$ escape,
        formatted ${expr}, etc.) and add it to given `result_token`.
        """
        peek = self.peek()
        if self.current_char == '\\' and peek == '$':
            # special escape in commands
            result_token.add_text('$')
            self.forward()  # skip "$"
        elif self.current_char == '$' and peek == '{':
            # formatted expression; read until "}"
            self.forward()
            self.forward()  # skip "${"
            expr_str = ''
            start_ln, start_col = self.current_lineno, self.current_col
            while self.current_char != '}':
                # check EOF
                if self.current_char is None or self.current_char == '\n':
                    self.error(ErrorType.UNCLOSED_FEXPR,
                               lineno=start_ln, col=start_col)
                expr_str += self.current_char
                self.forward()
            self.forward()  # skip "}"
            # create the Tokenizer
            tokenizer = Tokenizer(expr_str)
            tokenizer.current_lineno = start_ln
            tokenizer.current_col = start_col
            tokenizer.get_next_token()  # skip line_begin token
            result_token.add_expression(tokenizer)
        else:  # a normal character
            result_token.add_text(self._read_escapable_char())

    def handle_long_command(self):
        """Read a multi-line /*...*/ COMMAND token."""
        ln, col = self.current_lineno, self.current_col
        token = CommandToken(ln, col)
        self.forward()  # skip "/"
        self.forward()  # skip "*"
        while not (self.peek(0) == '*' and self.peek(1) == '/'):
            # check whether reach end of file
            if self.current_char is None:
                self.error(ErrorType.UNCLOSED_LONG_COMMAND, ln, col)
            # replace "\n" with " " (space)
            if self.current_char == '\n':
                self.current_char = ' '
            # read unit
            self._command_unit(token)
        self.forward()  # skip last character in command
        self.forward()  # skip "*"
        self.forward()  # skip "/"
        token.command_end()
        return token

    def handle_command(self):
        """Read a single-line / COMMAND token."""
        token = CommandToken(self.current_lineno, self.current_col)
        self.forward()  # skip slash "/"
        while self.current_char is not None and self.current_char != '\n':
            self._command_unit(token)
        token.command_end()
        return token
