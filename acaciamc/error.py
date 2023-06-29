"""Error definition for Acacia."""

__all__ = ['ErrorType', 'Error']

import enum

class ErrorType(enum.Enum):
    # Tokenizer
    INVALID_CHAR = 'Invalid character: "{char}"'
    INTEGER_REQUIRED = 'Expected base {base} integer'
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
    MODULE_NO_ATTRIBUTE = 'Module "{module}" does not have attribute "{attr}"'
    INVALID_OPERAND = 'Invalid operand(s) for "{operator}": {operand}'
    UNSUPPORTED_VAR_TYPE = 'Can\'t define variables of "{var_type}" type; ' \
        'To define alias to expressions, use "alia -> expr"'
    UNSUPPORTED_ARG_TYPE = 'Argument "{arg}" can\'t be "{arg_type}" type'
    UNSUPPORTED_RESULT_TYPE = 'Result type can\'t be "{result_type}" type'
    UNSUPPORTED_FIELD_TYPE = 'Entity field can\'t be "{field_type}" type'
    WRONG_ASSIGN_TYPE = 'Can\'t assign "{got}" to variable of "{expect}" type'
    WRONG_ARG_TYPE = 'Expect "{expect}" type for argument "{arg}", got "{got}"'
    WRONG_RESULT_TYPE = 'Expect "{expect}" type as result, got "{got}"'
    UNASSIGNABLE = 'The target is unassignable'
    WRONG_IF_CONDITION = '"if" conditions must be "bool", not "{got}"'
    WRONG_WHILE_CONDITION = '"while" conditions must be "bool", not "{got}"'
    ENDLESS_WHILE_LOOP = 'The "while" loop never ends because the conditon ' \
        'always evaluates to True'
    INVALID_TYPE_SPEC = 'Expecting a type specification, got "{got}"'
    INVALID_ETEMPLATE = 'Expecting an entity template, got "{got}"'
    ## INVALID_ARG_TYPE: `def f(a: 1)` "1" (int) is not a type
    ## UNSUPPORTED_ARG_TYPE: `def f(a = int)` args can't be of `type` type
    UNMATCHED_ARG_DEFAULT_TYPE = 'Specified type "{arg_type}" for arg ' \
        '"{arg}" does not match type of default value "{default_type}"'
    # ARG_MULTIPLE_VALUES is used by both Generator and Parser
    ARG_MULTIPLE_VALUES = 'Multiple values for argument "{arg}"'
    ATTR_MULTIPLE_DEFS = 'Multiple definitions for attribute "{attr}"'
    MISSING_ARG = 'Required argument "{arg}" is missing'
    RESULT_OUT_OF_SCOPE = 'Found "result" statement out of function'
    SELF_OUT_OF_SCOPE = 'Found "self" out of entity method'
    TOO_MANY_ARGS = 'Too many positional arguments'
    UNEXPECTED_KEYWORD_ARG = 'Unexpected keyword argument "{arg}"'
    UNCALLABLE = '"{expr_type}" is not callable'
    INVALID_CMD_FORMATTING = 'Invalid formatted expression of type ' \
        '"{expr_type}"'
    INVALID_RAWSCORE_SELECTOR = 'Invalid raw score selector of "{got}" type'
    INVALID_RAWSCORE_OBJECTIVE = 'Invalid raw score objective of "{got}" type'
    INVALID_CAST_ENTITY = 'Cast object should be an entity, not "{got}"'
    INVALID_CAST = 'Cast object should be an instance of the target template'
    INVALID_BIN_FUNC_ARG = 'Invalid argument "{arg}" for binary function: ' \
        '{message}'
    CANT_CREATE_INSTANCE = 'Can\'t create instance of "{type_}" type'
    INITIALIZER_RESULT = '{type_}.__init__ initializer should not produce ' \
        'result'
    CONST_ARITHMETIC = 'Arithmetic error when analyzing constant: {message}'
    REPEAT_ENTITY_META = 'Repeated entity meta "{meta}"'
    ENTITY_META = 'Error on entity meta "{meta}": {msg}'
    INVALID_ENTITY_META = 'Invalid entity meta name "{meta}"'
    MRO = 'Invalid base templates (failed to create MRO)'
    OVERRIDE_RESULT_MISMATCH = 'Override method "{name}" should have same ' \
        'result type "{expect}" as its parent, not "{got}"'
    # Compiler
    IO = 'I/O Error: {message}'
    MODULE_NOT_FOUND = 'Module not found: "{module}"'
    CIRCULAR_PARSE = 'File {file_!r} seems to call itself'
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
        res = self.type.value  # unformatted error
        res = res.format(**self.error_args)  # formatted
        res = '%s:%d:%d: %s' % (self.file, self.lineno, self.col, res)
        return res
