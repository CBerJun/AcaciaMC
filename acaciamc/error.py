"""Error definition for Acacia."""

__all__ = ['SourceLocation', 'ErrorType', 'Error', 'ErrFrame', 'traced_call']

from typing import Optional, Tuple, NamedTuple, List, Callable, Union

from acaciamc.localization import LocalizedEnum, localize


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


class ErrorType(LocalizedEnum):
    # Tokenizer
    INVALID_CHAR = "error.errortype.invalidchar"
    INTEGER_REQUIRED = "error.errortype.integerrequired"
    INT_OVERFLOW = "error.errortype.intoverflow"
    UNCLOSED_LONG_COMMENT = "error.errortype.unclosedlongcomment"
    UNCLOSED_LONG_COMMAND = "error.errortype.unclosedlongcommand"
    UNCLOSED_QUOTE = "error.errortype.unclosedquote"
    UNCLOSED_FEXPR = "error.errortype.unclosedfexpr"
    UNCLOSED_FONT = "error.errortype.unclosedfont"
    UNCLOSED_BRACKET = "error.errortype.unclosedbracket"
    UNMATCHED_BRACKET = "error.errortype.unmatchedbracket"
    UNMATCHED_BRACKET_PAIR = "error.errortype.unmatchedbracketpair"
    INVALID_UNICODE_ESCAPE = "error.errortype.invalidunicodeescape"
    INVALID_FONT = "error.errortype.invalidfont"
    CHAR_AFTER_CONTINUATION = "error.errortype.charaftercontinuation"
    EOF_AFTER_CONTINUATION = "error.errortype.eofaftercontinuation"
    INVALID_DEDENT = "error.errortype.invaliddedent"
    INTERFACE_PATH_EXPECTED = "error.errortype.interfacepathexpected"
    # Parser
    UNEXPECTED_TOKEN = "error.errortype.unexpectedtoken"
    EMPTY_BLOCK = "error.errortype.emptyblock"
    DONT_KNOW_ARG_TYPE = "error.errortype.dontknowargtype"
    DUPLICATE_ARG_DEF = "error.errortype.duplicateargdef"
    POSITIONED_ARG_AFTER_KEYWORD = "error.errortype.positionedargafterkeyword"
    NONDEFAULT_ARG_AFTER_DEFAULT = "error.errortype.nondefaultargafterdefault"
    INVALID_FUNC_PORT = "error.errortype.invalidfuncport"
    INVALID_VARDEF_STMT = "error.errortype.invalidvardefstmt"
    NONSTATIC_CONST_METHOD = "error.errortype.nonstaticconstmethod"
    # Command Generator
    NAME_NOT_DEFINED = "error.errortype.namenotdefined"
    HAS_NO_ATTRIBUTE = "error.errortype.hasnoattribute"
    MODULE_NO_ATTRIBUTE = "error.errortype.modulenoattribute"
    INVALID_OPERAND = "error.errortype.invalidoperand"
    INVALID_BOOLOP_OPERAND = "error.errortype.invalidboolopoperand"
    UNSUPPORTED_VAR_TYPE = "error.errortype.unsupportedvartype"
    UNSUPPORTED_ARG_TYPE = "error.errortype.unsupportedargtype"
    UNSUPPORTED_RESULT_TYPE = "error.errortype.unsupportedresulttype"
    UNSUPPORTED_EFIELD_TYPE = "error.errortype.unsupportedefieldtype"
    UNSUPPORTED_SFIELD_TYPE = "error.errortype.unsupportedsfieldtype"
    UNSUPPORTED_EFIELD_IN_STRUCT = "error.errortype.unsupportedefieldinstruct"
    SHADOWED_NAME = "error.errortype.shadowedname"
    WRONG_ASSIGN_TYPE = "error.errortype.wrongassigntype"
    WRONG_REF_TYPE = "error.errortype.wrongreftype"
    WRONG_CONST_TYPE = "error.errortype.wrongconsttype"
    WRONG_ARG_TYPE = "error.errortype.wrongargtype"
    WRONG_RESULT_TYPE = "error.errortype.wrongresulttype"
    WRONG_IF_CONDITION = "error.errortype.wrongifcondition"
    WRONG_WHILE_CONDITION = "error.errortype.wrongwhilecondition"
    CANT_REF = "error.errortype.cantref"
    CANT_REF_ARG = "error.errortype.cantrefarg"
    CANT_REF_RESULT = "error.errortype.cantrefresult"
    NOT_CONST = "error.errortype.notconst"
    NOT_CONST_NAME = "error.errortype.notconstname"
    NOT_CONST_ATTR = "error.errortype.notconstattr"
    ARG_NOT_CONST = "error.errortype.argnotconst"
    NONREF_ARG_DEFAULT_NOT_CONST = "error.errortype.nonrefargdefaultnotconst"
    ARG_DEFAULT_NOT_CONST = "error.errortype.argdefaultnotconst"
    RESULT_NOT_CONST = "error.errortype.resultnotconst"
    ELEMENT_NOT_CONST = "error.errortype.elementnotconst"
    MULTIPLE_RESULTS = "error.errortype.multipleresults"
    NON_RT_RESULT = "error.errortype.nonrtresult"
    NON_RT_NAME = "error.errortype.nonrtname"
    NON_RT_ATTR = "error.errortype.nonrtattr"
    ENDLESS_WHILE_LOOP = "error.errortype.endlesswhileloop"
    INVALID_TYPE_SPEC = "error.errortype.invalidtypespec"
    INVALID_ETEMPLATE = "error.errortype.invalidetemplate"
    INVALID_STEMPLATE = "error.errortype.invalidstemplate"
    UNMATCHED_ARG_DEFAULT_TYPE = "error.errortype.unmatchedargdefaulttype"
    # ARG_MULTIPLE_VALUES is used by both Generator and Parser
    ARG_MULTIPLE_VALUES = "error.errortype.argmultiplevalues"
    DUPLICATE_EFIELD = "error.errortype.duplicateefield"
    EFIELD_MULTIPLE_DEFS = "error.errortype.efieldmultipledefs"
    EMETHOD_MULTIPLE_DEFS = "error.errortype.emethodmultipledefs"
    MULTIPLE_VIRTUAL_METHOD = "error.errortype.multiplevirtualmethod"
    METHOD_ATTR_CONFLICT = "error.errortype.methodattrconflict"
    MULTIPLE_NEW_METHODS = "error.errortype.multiplenewmethods"
    CONST_NEW_METHOD = "error.errortype.constnewmethod"
    SFIELD_MULTIPLE_DEFS = "error.errortype.sfieldmultipledefs"
    MISSING_ARG = "error.errortype.missingarg"
    RESULT_OUT_OF_SCOPE = "error.errortype.resultoutofscope"
    SELF_OUT_OF_SCOPE = "error.errortype.selfoutofscope"
    NEW_OUT_OF_SCOPE = "error.errortype.newoutofscope"
    TOO_MANY_ARGS = "error.errortype.toomanyargs"
    UNEXPECTED_KEYWORD_ARG = "error.errortype.unexpectedkeywordarg"
    UNCALLABLE = "error.errortype.uncallable"
    NOT_ITERABLE = "error.errortype.notiterable"
    NO_GETITEM = "error.errortype.nogetitem"
    INVALID_ASSIGN_TARGET = "error.errortype.invalidassigntarget"
    INVALID_FEXPR = "error.errortype.invalidfexpr"
    INVALID_BIN_FUNC_ARG = "error.errortype.invalidbinfuncarg"
    CANT_CREATE_INSTANCE = "error.errortype.cantcreateinstance"
    CANT_CREATE_ENTITY = "error.errortype.cantcreateentity"
    ENTITY_NEW_RETURN_TYPE = "error.errortype.entitynewreturntype"
    CONST_ARITHMETIC = "error.errortype.constarithmetic"
    MRO = "error.errortype.mro"
    OVERRIDE_RESULT_MISMATCH = "error.errortype.overrideresultmismatch"
    OVERRIDE_RESULT_UNSTORABLE = "error.errortype.overrideresultunstorable"
    OVERRIDE_QUALIFIER = "error.errortype.overridequalifier"
    NOT_OVERRIDING = "error.errortype.notoverriding"
    INST_OVERRIDE_STATIC = "error.errortype.instoverridestatic"
    STATIC_OVERRIDE_INST = "error.errortype.staticoverrideinst"
    VIRTUAL_OVERRIDE_SIMPLE = "error.errortype.virtualoverridesimple"
    UNINITIALIZED_CONST = "error.errortype.uninitializedconst"
    INVALID_CONST_STMT = "error.errortype.invalidconststmt"
    POS_OFFSET_CTOR_ARG = "error.errortype.posoffsetctorarg"
    INVALID_POS_ALIGN = "error.errortype.invalidposalign"
    LIST_INDEX_OUT_OF_BOUNDS = "error.errortype.listindexoutofbounds"
    MAP_KEY_NOT_FOUND = "error.errortype.mapkeynotfound"
    INVALID_MAP_KEY = "error.errortype.invalidmapkey"
    LIST_MULTIMES_NON_LITERAL = "error.errortype.listmultimesnonliteral"
    INVALID_UPCAST = "error.errortype.invalidupcast"
    NEVER_RESULT = "error.errortype.neverresult"
    RESERVED_INTERFACE_PATH = "error.errortype.reservedinterfacepath"
    DUPLICATE_INTERFACE = "error.errortype.duplicateinterface"
    INTERFACE_PATH_EMPTY = "error.errortype.interfacepathempty"
    INTERFACE_PATH_SLASH_START = "error.errortype.interfacepathslashstart"
    INTERFACE_PATH_SLASH_END = "error.errortype.interfacepathslashend"
    INTERFACE_PATH_DOUBLE_SLASH = "error.errortype.interfacepathdoubleslash"
    INTERFACE_PATH_INVALID_CHAR = "error.errortype.interfacepathinvalidchar"
    # Compiler
    IO = "error.errortype.io"
    MODULE_NOT_FOUND = "error.errortype.modulenotfound"
    CIRCULAR_PARSE = "error.errortype.circularparse"
    # Any; should only be used by binary modules
    ANY = "error.errortype.any"


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
        res = self.type.localized  # unformatted error
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
        err.add_frame(ErrFrame(
            location,
            localize("error.tracedcall.calling") % func_repr,
            note
        ))
        raise
