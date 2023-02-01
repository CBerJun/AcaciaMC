import enum

__all__ = ['ErrorType', 'Error']

class ErrorType(enum.Enum):
    # Tokenizer
    INVALID_CHAR = 'Invalid character: "{char}"'
    INT_OVERFLOW = 'Integer overflows'
    UNCLOSED_LONG_COMMENT = 'Unclosed multi-line comment'
    UNCLOSED_LONG_COMMAND = 'Unclosed multi-line command'
    UNCLOSED_QUOTE = 'Unclosed double quote'
    UNCLOSED_FEXPR = 'Unclosed formatted expression'
    INVALID_UNICODE_ESCAPE = 'Invalid \\{escape_char} escape'
    CHAR_AFTER_LINE_CONTINUOUS = 'Unexpected character after line continuation'
    # Parser
    UNEXPECTED_TOKEN = 'Unexpected token {token}'
    WRONG_INDENT = 'Expect {expect} spaces indented, got {got}'
    EMPTY_BLOCK = 'Expect an indented block'
    DONT_KNOW_ARG_TYPE = 'Type of argument or its default value ' \
        'must be specified: "{arg}"'
    DUPLICATE_ARG_DEF = 'Duplicate argument "{arg}" in function definition'
    POSITIONED_ARG_AFTER_KEYWORD = 'Positional argument after keyword'
    INVALID_ASSIGN_TARGET = 'Invalid assignment target'
    INVALID_BIND_TARGET = 'Invalid bind target'
    # Command Generator
    NAME_NOT_DEFINED = 'Name "{name}" is not defined'
    HAS_NO_ATTRIBUTE = '"{value_type}" objects have no attribute "{attr}"'
    INVALID_OPERAND = 'Invalid operand(s) for "{operator}": {operand}'
    UNSUPPORTED_VAR_TYPE = 'Can\'t define variables of "{var_type}" type; ' \
        'To define alias to expressions, use "alia -> expr"'
    UNSUPPORTED_ARG_TYPE = 'Argument "{arg}" can\'t be "{arg_type}" type'
    UNSUPPORTED_RESULT_TYPE = 'Result type can\'t be "{result_type}" type'
    WRONG_ASSIGN_TYPE = 'Can\'t assign "{got}" to variable of "{expect}" type'
    WRONG_ARG_TYPE = 'Expect "{expect}" type for argument "{arg}", got "{got}"'
    WRONG_RESULT_TYPE = 'Expect "{expect}" type as result, got "{got}"'
    UNASSIGNABLE = 'The target is unassignable'
    BIND_TARGET_EXISTS = 'Target to bind already has a value'
    FUNC_NAME_EXISTS = 'Can\'t define functions using an existing name ' \
        '"{name}"'
    WRONG_IF_CONDITION = '"if" conditions must be "bool", not "{got}"'
    WRONG_WHILE_CONDITION = '"while" conditions must be "bool", not "{got}"'
    ENDLESS_WHILE_LOOP = 'The "while" loop never ends because the conditon ' \
        'always evaluates to True'
    INVALID_RESULT_TYPE = 'Specified result type "{got}" is not a type'
    INVALID_ARG_TYPE = 'Type "{arg_type}" for argument "{arg}" is not a type'
    ## INVALID_ARG_TYPE: `def f(a: 1)` "1" (int) is not a type
    ## UNSUPPORTED_ARG_TYPE: `def f(a = int)` args can't be of `type` type
    UNMATCHED_ARG_DEFAULT_TYPE = 'Specified type "{arg_type}" for arg ' \
        '"{arg}" does not match type of default value "{default_type}"'
    # ARG_MULTIPLE_VALUES is used by both Generator and Parser
    ARG_MULTIPLE_VALUES = 'Multiple values for argument "{arg}"'
    MISSING_ARG = 'Required argument "{arg}" is missing'
    RESULT_OUT_OF_SCOPE = 'Found "result" statement out of function'
    TOO_MANY_ARGS = 'Too many positional arguments'
    UNEXPECTED_KEYWORD_ARG = 'Unexpected keyword argument "{arg}"'
    UNCALLABLE = '"{expr_type}" is not callable'
    INVALID_CMD_FORMATTING = 'Invalid formatted expression of type ' \
        '"{expr_type}"'
    INVALID_RAWSCORE_SELECTOR = 'Invalid raw score selector of "{got}" type'
    INVALID_RAWSCORE_OBJECTIVE = 'Invalid raw score objective of "{got}" type'
    INVALID_BIN_FUNC_ARG = 'Invalid argument "{arg}" for binary function ' \
        ': {message}'
    CANT_CREATE_INSTANCE = 'Can\'t create instance of "{type_}" type'
    INITIALIZER_RESULT = '{type_}.__init__ initializer should not produce ' \
        'result'
    CONST_ARITHMETIC = 'Arithmetic error when analyzing constant: {message}'
    # Compiler
    IO = 'I/O Error: {message}'
    MODULE_NOT_FOUND = 'Module not found: "{name}"'
    # Any; should only be used by binary modules
    ANY = '{message}'

class Error(Exception):
    def __init__(self, err_type: ErrorType, lineno, col, file, **kwargs):
        # lineno:int & col:int & file:str postion of error
        # **kwargs:str will be formated to the message
        self.lineno = lineno
        self.col = col
        self.error_args = kwargs
        self.type = err_type
        self.file = file
        super().__init__()
    
    def __str__(self):
        res = self.type.value # unformatted error
        res = res.format(**self.error_args) # formatted
        res = '%s:%d:%d: %s' % (self.file, self.lineno, self.col, res)
        return res
