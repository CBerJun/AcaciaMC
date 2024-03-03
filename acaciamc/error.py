"""Error definition for Acacia."""

__all__ = ['SourceLocation', 'ErrorType', 'Error', 'ErrFrame']

from typing import Optional, Tuple, NamedTuple, List
import enum

class SourceLocation:
    """Represent a location in a source file for showing errors."""
    def __init__(
            self, file: Optional[str] = None,
            linecol: Optional[Tuple[int, int]] = None):
        self.file = file
        self.linecol = linecol

    def file_set(self) -> bool:
        return self.file is not None

    def linecol_set(self) -> bool:
        return self.linecol is not None

    def __str__(self) -> str:
        if self.file is None:
            return "<unknown>"
        if self.linecol is None:
            return self.file
        return "%s:%d:%d" % (self.file, self.linecol[0], self.linecol[1])

class ErrorType(enum.Enum):
    # Tokenizer
    INVALID_CHAR = 'Invalid character: "{char}"'
    INTEGER_REQUIRED = 'Expected base {base} integer'
    INT_OVERFLOW = 'Integer overflows'
    UNCLOSED_LONG_COMMENT = 'Unclosed multi-line comment'
    UNCLOSED_LONG_COMMAND = 'Unclosed multi-line command'
    UNCLOSED_QUOTE = 'Unclosed double quote'
    UNCLOSED_FEXPR = 'Unclosed formatted expression'
    UNCLOSED_FONT = 'Unclosed font specifier'
    UNCLOSED_BRACKET = 'Unclosed {char!r}'
    UNMATCHED_BRACKET = 'Unmatched {char!r}'
    UNMATCHED_BRACKET_PAIR = 'Closing bracket {close!r} does not match ' \
        'opening bracket {open!r}'
    INVALID_UNICODE_ESCAPE = 'Invalid \\{escape_char} escape'
    INVALID_FONT = 'Invalid font specifier: "{font}"'
    CHAR_AFTER_CONTINUATION = 'Unexpected character after line continuation'
    EOF_AFTER_CONTINUATION = 'End of file in multi-line statement'
    INVALID_DEDENT = 'Dedent does not match any outer indentation level'
    # Parser
    UNEXPECTED_TOKEN = 'Unexpected token {token}'
    EMPTY_BLOCK = 'Expect an indented block'
    DONT_KNOW_ARG_TYPE = 'Type of argument or its default value ' \
        'must be specified: "{arg}"'
    DUPLICATE_ARG_DEF = 'Duplicate argument "{arg}" in function definition'
    POSITIONED_ARG_AFTER_KEYWORD = 'Positional argument after keyword'
    NONDEFAULT_ARG_AFTER_DEFAULT = 'Non-default argument after default ' \
        'argument'
    INVALID_FUNC_PORT = 'This type of function can\'t use qualifier "{port}"'
    INVALID_VARDEF_STMT = 'Invalid variable definition target'
    # Command Generator
    NAME_NOT_DEFINED = 'Name "{name}" is not defined'
    HAS_NO_ATTRIBUTE = '"{value_type}" objects have no attribute "{attr}"'
    MODULE_NO_ATTRIBUTE = 'Module "{module}" does not have attribute "{attr}"'
    INVALID_OPERAND = 'Invalid operand(s) for "{operator}": {operand}'
    INVALID_BOOLOP_OPERAND = 'Invalid operand for boolean operator ' \
        '"{operator}": "{operand}"'
    UNSUPPORTED_VAR_TYPE = 'Can\'t define variables of "{var_type}" type'
    UNSUPPORTED_ARG_TYPE = 'Runtime argument "{arg}" passed by value can\'t ' \
        'be "{arg_type}" type'
    UNSUPPORTED_RESULT_TYPE = 'Result type can\'t be "{result_type}" type'
    UNSUPPORTED_EFIELD_TYPE = 'Entity field can\'t be "{field_type}" type'
    UNSUPPORTED_SFIELD_TYPE = 'Struct field can\'t be "{field_type}" type'
    UNSUPPORTED_EFIELD_IN_STRUCT = 'Entity field can\'t be struct ' \
        '"{template}" type bacause it contains field of "{field_type}" type'
    SHADOWED_NAME = 'Shadowed name "{name}"'
    WRONG_ASSIGN_TYPE = 'Can\'t assign "{got}" to variable of "{expect}" type'
    WRONG_REF_TYPE = 'Specified reference type is "{anno}" but got "{got}"'
    WRONG_CONST_TYPE = 'Specified const type for "{name}" is "{anno}" but ' \
        'got "{got}"'
    WRONG_ARG_TYPE = 'Expect "{expect}" type for argument "{arg}", got "{got}"'
    WRONG_RESULT_TYPE = 'Expect "{expect}" type as result, got "{got}"'
    WRONG_IF_CONDITION = '"if" conditions must be "bool", not "{got}"'
    WRONG_WHILE_CONDITION = '"while" conditions must be "bool", not "{got}"'
    CANT_REF = 'Cannot reference unassignable expression'
    CANT_REF_ARG = 'Value for reference argument "{arg}" is not assignable'
    CANT_REF_RESULT = 'Value for reference result is not assignable'
    NOT_CONST = 'Value for "{name}" in const definition is not a constant'
    NOT_CONST_EXPR = 'Expression in const function is not a constant'
    ARG_NOT_CONST = 'Value for const argument "{arg}" is not a constant'
    NONREF_ARG_DEFAULT_NOT_CONST = 'Default value for non-reference ' \
        'argument "{arg}" must be a constant'
    ARG_DEFAULT_NOT_CONST = 'Default value for argument "{arg}" in compile ' \
        'time function must be a constant'
    RESULT_NOT_CONST = 'Result is expected to be a constant'
    ELEMENT_NOT_CONST = 'Element in list or map must be a constant'
    MULTIPLE_RESULTS = 'Multiple "result" statements in inline function that' \
        ' uses const or reference result'
    ENDLESS_WHILE_LOOP = 'The "while" loop never ends because the conditon ' \
        'always evaluates to True'
    INVALID_TYPE_SPEC = 'Expecting a type specifier, got "{got}"'
    INVALID_ETEMPLATE = 'Expecting an entity template, got "{got}"'
    INVALID_STEMPLATE = 'Expecting a struct template, got "{got}"'
    UNMATCHED_ARG_DEFAULT_TYPE = 'Specified type "{arg_type}" for arg ' \
        '"{arg}" does not match type of default value "{default_type}"'
    # ARG_MULTIPLE_VALUES is used by both Generator and Parser
    ARG_MULTIPLE_VALUES = 'Multiple values for argument "{arg}"'
    EFIELD_MULTIPLE_DEFS = 'Multiple definitions for entity attribute "{attr}"'
    SFIELD_MULTIPLE_DEFS = 'Multiple definitions for struct attribute "{attr}"'
    MISSING_ARG = 'Required argument "{arg}" is missing'
    RESULT_OUT_OF_SCOPE = 'Found "result" out of function'
    SELF_OUT_OF_SCOPE = 'Found "self" out of entity method'
    TOO_MANY_ARGS = 'Too many positional arguments'
    UNEXPECTED_KEYWORD_ARG = 'Unexpected keyword argument "{arg}"'
    UNCALLABLE = '"{expr_type}" is not callable'
    NOT_ITERABLE = '"{type_}" is not iterable'
    NO_GETITEM = '"{type_}" is not subscriptable'
    NO_SETITEM = '"{type_}" does not support item write access'
    INVALID_ASSIGN_TARGET = 'Invalid assignment target'
    INVALID_FEXPR = 'Invalid formatted expression'
    INVALID_RAWSCORE_SELECTOR = 'Invalid raw score selector of "{got}" type'
    INVALID_RAWSCORE_OBJECTIVE = 'Invalid raw score objective of "{got}" type'
    INVALID_CAST_ENTITY = 'Cast object should be an entity, not "{got}"'
    INVALID_CAST = 'Cast object should be an instance of the target template'
    INVALID_BIN_FUNC_ARG = 'Invalid argument "{arg}" for binary function: ' \
        '{message}'
    CANT_CREATE_INSTANCE = 'Can\'t create instance of "{type_}" type'
    INITIALIZER_RESULT = '__init__ initializer for "{type_}" should not ' \
        'produce result'
    INITIALIZER_NOT_CALLABLE = '__init__ initializer for "{type_}" should ' \
        'be callable, not "{got}"'
    CONST_ARITHMETIC = 'Arithmetic error when analyzing constant: {message}'
    REPEAT_ENTITY_META = 'Repeated entity meta "{meta}"'
    ENTITY_META = 'Error on entity meta "{meta}": {msg}'
    INVALID_ENTITY_META = 'Invalid entity meta name "{meta}"'
    MRO = 'Invalid base templates (failed to create MRO)'
    OVERRIDE_RESULT_MISMATCH = 'Override method "{name}" should have same ' \
        'result type "{expect}" as its parent, not "{got}"'
    OVERRIDE_RESULT_UNKNOWN = 'Virtual/override inline method "{name}" ' \
        'must have its result specified; explicitly specify None if it ' \
        'doesn\'t produce a meaningful result'
    OVERRIDE_RESULT_UNSTORABLE = 'Virtual/override inline method "{name}" ' \
        'can not use "{type_}" as result type'
    OVERRIDE_QUALIFIER = 'Override method "{name}" should have qualifier ' \
        '"override", not "{got}"'
    NOT_OVERRIDING = 'Method "{name}" is marked as "override" but did not ' \
        'actually override a virtual method'
    UNINITIALIZED_CONST = 'Uninitialized variable in compile time function'
    INVALID_CONST_STMT = 'Invalid statement in compile time function'
    POS_OFFSET_CTOR_ARG = 'At most one of the arguments "{axis}" and "{axis}' \
        '_abs" can be float'
    INVALID_POS_ALIGN = 'Invalid position alignment "{align}"'
    LIST_INDEX_OUT_OF_BOUNDS = 'List with length {length} got out of ' \
        'bounds index {index}'
    MAP_KEY_NOT_FOUND = 'Map key not found'
    INVALID_MAP_KEY = 'Invalid map key'
    LIST_MULTIMES_NON_LITERAL = 'List can only be multiplied by literal int'
    RESULT_BIND_OUT_OF_SCOPE = "Can't bind to result when out of function " \
        "or inside non-inline function"
    NEVER_RESULT = "The function should have set its result but didn't"
    RESERVED_INTERFACE_PATH = 'Reserved interface path: {path}'
    DUPLICATE_INTERFACE = 'Multiple definitions of interface: {path}'
    # Compiler
    IO = 'I/O Error: {message}'
    MODULE_NOT_FOUND = 'Module not found: "{module}"'
    CIRCULAR_PARSE = 'File {file_!r} seems to call itself'
    # Any; should only be used by binary modules
    ANY = '{message}'

class ErrFrame(NamedTuple):
    location: SourceLocation
    msg: str
    note: Optional[str]

class Error(Exception):
    def __init__(self, err_type: ErrorType, **kwargs):
        self.error_args = kwargs
        self.type = err_type
        self.location = SourceLocation()
        self.frames: List[ErrFrame] = []
        super().__init__()

    def __str__(self):
        res = self.type.value  # unformatted error
        res = res.format(**self.error_args)  # formatted
        res = '%s: %s' % (self.location, res)
        return res

    def full_msg(self) -> str:
        return (
            "compiler error:"
            + ("\n" if self.frames else " ")
            + "".join(
                "  %s: %s" % (frame.location, frame.msg)
                + ("\n    %s" % frame.note if frame.note else "")
                + "\n"
                for frame in reversed(self.frames)
            )
            + str(self)
        )

    def add_frame(self, frame: ErrFrame):
        self.frames.append(frame)
