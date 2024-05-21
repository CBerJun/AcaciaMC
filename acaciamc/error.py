"""Error definition for Acacia."""

__all__ = ['SourceLocation', 'ErrorType', 'Error', 'ErrFrame', 'traced_call']

from typing import Optional, Tuple, NamedTuple, List, Callable, Union
import enum
import acaciamc.localization
from acaciamc.localization import get_text

lang = acaciamc.localization.get_lang()

def localize(text):
    return get_text(text, lang)

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
    INVALID_CHAR = localize("error.errortype.invalidchar")
    INTEGER_REQUIRED = localize("error.errortype.integerrequired")
    INT_OVERFLOW = localize("error.errortype.intoverflow")
    UNCLOSED_LONG_COMMENT = localize("error.errortype.unclosedlongcomment")
    UNCLOSED_LONG_COMMAND = localize("error.errortype.unclosedlongcommand")
    UNCLOSED_QUOTE = localize("error.errortype.unclosedquote")
    UNCLOSED_FEXPR = localize("error.errortype.unclosedfexpr")
    UNCLOSED_FONT = localize("error.errortype.unclosedfont")
    UNCLOSED_BRACKET = localize("error.errortype.unclosedbracket")
    UNMATCHED_BRACKET = localize("error.errortype.unmatchedbracket")
    UNMATCHED_BRACKET_PAIR = localize("error.errortype.unmatchedbracketpair")
    INVALID_UNICODE_ESCAPE = localize("error.errortype.invalidunicodeescape")
    INVALID_FONT = localize("error.errortype.invalidfont")
    CHAR_AFTER_CONTINUATION = localize("error.errortype.charaftercontinuation")
    EOF_AFTER_CONTINUATION = localize("error.errortype.eofaftercontinuation")
    INVALID_DEDENT = localize("error.errortype.invaliddedent")
    # Parser
    UNEXPECTED_TOKEN = localize("error.errortype.unexpectedtoken")
    EMPTY_BLOCK = localize("error.errortype.emptyblock")
    DONT_KNOW_ARG_TYPE = localize("error.errortype.dontknowargtype")
    DUPLICATE_ARG_DEF = localize("error.errortype.duplicateargdef")
    POSITIONED_ARG_AFTER_KEYWORD = localize("error.errortype.positionedargafterkeyword")
    NONDEFAULT_ARG_AFTER_DEFAULT = localize("error.errortype.nondefaultargafterdefault")
    INVALID_FUNC_PORT = localize("error.errortype.invalidfuncport")
    INVALID_VARDEF_STMT = localize("error.errortype.invalidvardefstmt")
    NONSTATIC_CONST_METHOD = localize("error.errortype.nonstaticconstmethod")
    # Command Generator
    NAME_NOT_DEFINED = localize("error.errortype.namenotdefined")
    HAS_NO_ATTRIBUTE = localize("error.errortype.hasnoattribute")
    MODULE_NO_ATTRIBUTE = localize("error.errortype.modulenoattribute")
    INVALID_OPERAND = localize("error.errortype.invalidoperand")
    INVALID_BOOLOP_OPERAND = localize("error.errortype.invalidboolopoperand")
    UNSUPPORTED_VAR_TYPE = localize("error.errortype.unsupportedvartype")
    UNSUPPORTED_ARG_TYPE = localize("error.errortype.unsupportedargtype")
    UNSUPPORTED_RESULT_TYPE = localize("error.errortype.unsupportedresulttype")
    UNSUPPORTED_EFIELD_TYPE = localize("error.errortype.unsupportedefieldtype")
    UNSUPPORTED_SFIELD_TYPE = localize("error.errortype.unsupportedsfieldtype")
    UNSUPPORTED_EFIELD_IN_STRUCT = localize("error.errortype.unsupportedefieldinstruct")
    SHADOWED_NAME = localize("error.errortype.shadowedname")
    WRONG_ASSIGN_TYPE = localize("error.errortype.wrongassigntype")
    WRONG_REF_TYPE = localize("error.errortype.wrongreftype")
    WRONG_CONST_TYPE = localize("error.errortype.wrongconsttype")
    WRONG_ARG_TYPE = localize("error.errortype.wrongargtype")
    WRONG_RESULT_TYPE = localize("error.errortype.wrongresulttype")
    WRONG_IF_CONDITION = localize("error.errortype.wrongifcondition")
    WRONG_WHILE_CONDITION = localize("error.errortype.wrongwhilecondition")
    CANT_REF = localize("error.errortype.cantref")
    CANT_REF_ARG = localize("error.errortype.cantrefarg")
    CANT_REF_RESULT = localize("error.errortype.cantrefresult")
    NOT_CONST = localize("error.errortype.notconst")
    NOT_CONST_NAME = localize("error.errortype.notconstname")
    NOT_CONST_ATTR = localize("error.errortype.notconstattr")
    ARG_NOT_CONST = localize("error.errortype.argnotconst")
    NONREF_ARG_DEFAULT_NOT_CONST = localize("error.errortype.nonrefargdefaultnotconst")
    ARG_DEFAULT_NOT_CONST = localize("error.errortype.argdefaultnotconst")
    RESULT_NOT_CONST = localize("error.errortype.resultnotconst")
    ELEMENT_NOT_CONST = localize("error.errortype.elementnotconst")
    MULTIPLE_RESULTS = localize("error.errortype.multipleresults")
    NON_RT_RESULT = localize("error.errortype.nonrtresult")
    NON_RT_NAME = localize("error.errortype.nonrtname")
    NON_RT_ATTR = localize("error.errortype.nonrtattr")
    ENDLESS_WHILE_LOOP = localize("error.errortype.endlesswhileloop")
    INVALID_TYPE_SPEC = localize("error.errortype.invalidtypespec")
    INVALID_ETEMPLATE = localize("error.errortype.invalidetemplate")
    INVALID_STEMPLATE = localize("error.errortype.invalidstemplate")
    UNMATCHED_ARG_DEFAULT_TYPE = localize("error.errortype.unmatchedargdefaulttype")
    # ARG_MULTIPLE_VALUES is used by both Generator and Parser
    ARG_MULTIPLE_VALUES = localize("error.errortype.argmultiplevalues")
    DUPLICATE_EFIELD = localize("error.errortype.duplicateefield")
    EFIELD_MULTIPLE_DEFS = localize("error.errortype.efieldmultipledefs")
    EMETHOD_MULTIPLE_DEFS = localize("error.errortype.emethodmultipledefs")
    MULTIPLE_VIRTUAL_METHOD = localize("error.errortype.multiplevirtualmethod")
    METHOD_ATTR_CONFLICT = localize("error.errortype.methodattrconflict")
    MULTIPLE_NEW_METHODS = localize("error.errortype.multiplenewmethods")
    CONST_NEW_METHOD = localize("error.errortype.constnewmethod")
    SFIELD_MULTIPLE_DEFS = localize("error.errortype.sfieldmultipledefs")
    MISSING_ARG = localize("error.errortype.missingarg")
    RESULT_OUT_OF_SCOPE = localize("error.errortype.resultoutofscope")
    SELF_OUT_OF_SCOPE = localize("error.errortype.selfoutofscope")
    NEW_OUT_OF_SCOPE = localize("error.errortype.newoutofscope")
    TOO_MANY_ARGS = localize("error.errortype.toomanyargs")
    UNEXPECTED_KEYWORD_ARG = localize("error.errortype.unexpectedkeywordarg")
    UNCALLABLE = localize("error.errortype.uncallable")
    NOT_ITERABLE = localize("error.errortype.notiterable")
    NO_GETITEM = localize("error.errortype.nogetitem")
    INVALID_ASSIGN_TARGET = localize("error.errortype.invalidassigntarget")
    INVALID_FEXPR = localize("error.errortype.invalidfexpr")
    INVALID_BIN_FUNC_ARG = localize("error.errortype.invalidbinfuncarg")
    CANT_CREATE_INSTANCE = localize("error.errortype.cantcreateinstance")
    CANT_CREATE_ENTITY = localize("error.errortype.cantcreateentity")
    ENTITY_NEW_RETURN_TYPE = localize("error.errortype.entitynewreturntype")
    CONST_ARITHMETIC = localize("error.errortype.constarithmetic")
    MRO = localize("error.errortype.mro")
    OVERRIDE_RESULT_MISMATCH = localize("error.errortype.overrideresultmismatch")
    OVERRIDE_RESULT_UNSTORABLE = localize("error.errortype.overrideresultunstorable")
    OVERRIDE_QUALIFIER = localize("error.errortype.overridequalifier")
    NOT_OVERRIDING = localize("error.errortype.notoverriding")
    INST_OVERRIDE_STATIC = localize("error.errortype.instoverridestatic")
    STATIC_OVERRIDE_INST = localize("error.errortype.staticoverrideinst")
    VIRTUAL_OVERRIDE_SIMPLE = localize("error.errortype.virtualoverridesimple")
    UNINITIALIZED_CONST = localize("error.errortype.uninitializedconst")
    INVALID_CONST_STMT = localize("error.errortype.invalidconststmt")
    POS_OFFSET_CTOR_ARG = localize("error.errortype.posoffsetctorarg")
    INVALID_POS_ALIGN = localize("error.errortype.invalidposalign")
    LIST_INDEX_OUT_OF_BOUNDS = localize("error.errortype.listindexoutofbounds")
    MAP_KEY_NOT_FOUND = localize("error.errortype.mapkeynotfound")
    INVALID_MAP_KEY = localize("error.errortype.invalidmapkey")
    LIST_MULTIMES_NON_LITERAL = localize("error.errortype.listmultimesnonliteral")
    INVALID_UPCAST = localize("error.errortype.invalidupcast")
    NEVER_RESULT = localize("error.errortype.neverresult")
    RESERVED_INTERFACE_PATH = localize("error.errortype.reservedinterfacepath")
    DUPLICATE_INTERFACE = localize("error.errortype.duplicateinterface")
    # Compiler
    IO = localize("error.errortype.io")
    MODULE_NOT_FOUND = localize("error.errortype.modulenotfound")
    CIRCULAR_PARSE = localize("error.errortype.circularparse")
    # Any; should only be used by binary modules
    ANY = localize("error.errortype.any")

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
            localize("error.fullmsg.compilererror")
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

def traced_call(
    func: Callable, location: Union[SourceLocation, str, None],
    source: Optional[SourceLocation], func_repr: str,
    *args, **kwds
):
    try:
        return func(*args, **kwds)
    except Error as err:
        if location is None:
            location = SourceLocation()
        elif isinstance(location, str):
            location = SourceLocation(file=location)
        if source is not None and source.file_set():
            note = localize("error.tracedcall.note") % source
        else:
            note = None
        err.add_frame(ErrFrame(location, localize("error.tracedcall.calling") % func_repr, note))
        raise
