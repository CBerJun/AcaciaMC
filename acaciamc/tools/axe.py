"""Argument Axe - argument parsing tool for binary functions"""

__all__ = [
    # Decorators
    "chop", "arg", "slash", "star", "star_arg", "kwds",
    # Overload interfaces
    "OverloadChopped", "overload", "overload_versioned",
    # Converters
    "Converter", "AnyValue", "Typed", "Multityped", "LiteralInt",
    "LiteralFloat", "LiteralString", "LiteralBool", "Nullable", "AnyOf",
    "Iterator", "Selector", "LiteralIntEnum", "LiteralStringEnum", "ListOf",
    "MapOf", "PlayerSelector", "RangedLiteralInt", "Callable", "PosXZ",
    "CTConverter", "UConverter", "CTTyped", "CTIterator", "CTReference",
    "Constant", "AnyRT",
    # Exception
    "ChopError", "ArgumentError"
]

from typing import (
    Callable as PyCallable, Optional, Type, Any, Union, List, Tuple, Dict,
    Iterable, TYPE_CHECKING
)
from itertools import chain
from functools import partial
import inspect

# `import acaciamc.mccmdgen.expression as acacia` won't work in 3.6
# because of a Python bug (see https://bugs.python.org/issue23203)
from acaciamc.mccmdgen import expression as acacia
from acaciamc.ctexec import expr as acaciact
from acaciamc.mccmdgen.datatype import DataType
from acaciamc.error import Error as AcaciaError, ErrorType

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.tools.versionlib import VersionRequirement
    from acaciamc.mccmdgen.mcselector import MCSelector

### Exception

class ChopError(Exception):
    """Wrong use of Axe."""
    pass

class ArgumentError(Exception):
    """Can be raised when user is not satisfied with an argument in
    an implementation of binary function that is managed with Axe.
    """
    def __init__(self, arg: str, message: str) -> None:
        """Report error on `arg`."""
        super().__init__(arg, message)
        self.arg = arg
        self.message = message

class _WrongArgTypeError(Exception):
    pass

_PE_NOT_CONST = 1
_PE_NOT_RT = 2

class _PreconvertError(Exception):
    def __init__(self, code: int, origin: "_EXPR_T"):
        super().__init__(code, origin)
        self.code = code
        self.origin = origin

    def show(self, arg: str) -> str:
        o = _exprrepr(self.origin)
        if self.code == _PE_NOT_CONST:
            return (f'const argument "{arg}" received non-const value of '
                    f'type {o}')
        if self.code == _PE_NOT_RT:
            return (f'argument "{arg}" is expecting a value that exists '
                    f'at runtime, got {o}')
        raise ValueError(f'unknown error code {self.code}')

### Building Stage

_BP_ARG = 1
_BP_STAR = 2
_BP_STAR_ARG = 3
_BP_SLASH = 4
_BP_KWDS = 5

_EXPR_T = Union[acacia.AcaciaExpr, acaciact.CTExpr]
_CONVERTER_T = Union["Converter", "CTConverter"]

class _Argument:
    def __init__(self, name: str, rename: str, converter: _CONVERTER_T):
        self.name = name
        self.rename = rename
        self.converter = converter

    def set_default(self, value):
        self._default = value

    def has_default(self):
        return hasattr(self, "_default")

    def get_default(self):
        if self.has_default():
            return self._default
        raise ValueError("don't have default")

class _ArgumentList:
    def __init__(self, name: str, rename: str, converter: _CONVERTER_T):
        self.name = name
        self.rename = rename
        self.converter = converter

class _BuildingParser(List[Tuple[int, Any]]):
    def __init__(self, target: PyCallable):
        super().__init__()
        self._target = target

    def push_component(self, type_: int, definition=None):
        self.insert(0, (type_, definition))

    def get_target(self):
        return self._target

def _parser_component(func: PyCallable[[_BuildingParser], Any]):
    """Decorator that creates decorators that build the parser.
    If the target function returns None, the building parser will
    then be returned in decorated decorator.
    """
    def _decorated(user_input: Union[PyCallable, _BuildingParser]):
        if isinstance(user_input, _BuildingParser):
            p = user_input
        else:
            assert callable(user_input)
            p = _BuildingParser(user_input)
        res = func(p)
        if res is None:
            return p
        else:
            return res
    return _decorated

### Building Stage Interface

_TYPED_TYPE = Union[DataType, Type[DataType]]
_ARG_TYPE = Union[_TYPED_TYPE, _CONVERTER_T]
_NO_DEFAULT = object()

def _converter(type_: _ARG_TYPE):
    if isinstance(type_, (Converter, CTConverter)):
        return type_
    elif isinstance(type_, acaciact.CTDataType):
        return CTTyped(type_)
    else:
        return Typed(type_)

def arg(name: str, type_: _ARG_TYPE, rename: Optional[str] = None,
        default: Any = _NO_DEFAULT):
    """Return a decorator for adding an argument"""
    if rename is None:
        rename = name
    converter = _converter(type_)
    definition = _Argument(name, rename, converter)
    if default is not _NO_DEFAULT:
        definition.set_default(default)
    @_parser_component
    def _decorator(building: _BuildingParser):
        building.push_component(_BP_ARG, definition)
    return _decorator

@_parser_component
def slash(building: _BuildingParser):
    """Indicate arguments before are position-only."""
    building.push_component(_BP_SLASH)

@_parser_component
def star(building: _BuildingParser):
    """Indicate arguments after are keyword-only."""
    building.push_component(_BP_STAR)

def _arg_list(bd_type: int, name: str, type_: _ARG_TYPE,
              rename: Optional[str] = None):
    if rename is None:
        rename = name
    converter = _converter(type_)
    @_parser_component
    def _decorator(building: _BuildingParser):
        building.push_component(
            bd_type, _ArgumentList(name, rename, converter)
        )
    return _decorator

def star_arg(name: str, type_: _ARG_TYPE, rename: Optional[str] = None):
    """Catch all positional arguments. Arguments after are keyword-only."""
    return _arg_list(_BP_STAR_ARG, name, type_, rename)

def kwds(name: str, type_: _ARG_TYPE, rename: Optional[str] = None):
    """Catch all keyword arguments. Must at the end."""
    return _arg_list(_BP_KWDS, name, type_, rename)

### Argument converter

class Converter:
    def wrong_argument(self):
        """Used by `convert` method to raise an error."""
        raise _WrongArgTypeError

    def get_show_name(self) -> str:
        """Get show name."""
        raise NotImplementedError

    def convert(self, origin: acacia.AcaciaExpr):
        """Converts the argument.
        Can use `wrong_argument` method when failed.
        """
        raise NotImplementedError

class CTConverter:
    def wrong_argument(self):
        """Used by `convert` method to raise an error."""
        raise _WrongArgTypeError

    def crepr(self) -> str:
        raise NotImplementedError

    def cconvert(self, origin: acaciact.CTExpr):
        raise NotImplementedError

class UConverter(CTConverter, Converter):
    unbox_ctptr = True

    def crepr(self) -> str:
        return self.get_show_name()

    def uconvert(self, origin: _EXPR_T):
        raise NotImplementedError

    def convert(self, origin: acacia.AcaciaExpr):
        return self.uconvert(origin)

    def cconvert(self, origin: acaciact.CTExpr):
        if self.unbox_ctptr:
            origin = abs(origin)
        return self.uconvert(origin)

class AnyValue(UConverter):
    """Accepts any value."""
    def get_show_name(self) -> str:
        return "Any"

    def uconvert(self, origin):
        return origin

class Constant(CTConverter):
    def crepr(self) -> str:
        return "Any"

    def cconvert(self, origin):
        return origin

class AnyRT(Converter):
    def get_show_name(self) -> str:
        return "Any"

    def convert(self, origin: acacia.AcaciaExpr):
        return origin

def _type_checker(value: acacia.AcaciaExpr, type_: _TYPED_TYPE):
    if isinstance(type_, DataType):
        return type_.is_type_of(value)
    else:
        assert issubclass(type_, DataType)
        return value.data_type.matches_cls(type_)

def _type_to_str(type_: _TYPED_TYPE):
    if isinstance(type_, DataType):
        return str(type_)
    else:
        return type_.name_no_generic()

class Typed(Converter):
    """Accepts value of specified data type."""
    def __init__(self, type_: _TYPED_TYPE):
        super().__init__()
        self.type = type_

    def get_show_name(self) -> str:
        return _type_to_str(self.type)

    def convert(self, origin: acacia.AcaciaExpr):
        if not _type_checker(origin, self.type):
            self.wrong_argument()
        return origin

class Multityped(Converter):
    """Accepts value of several types."""
    def __init__(self, types: Iterable[_TYPED_TYPE]):
        super().__init__()
        self.types = tuple(types)

    def get_show_name(self) -> str:
        return " / ".join(map(_type_to_str, self.types))

    def convert(self, origin: acacia.AcaciaExpr):
        if not any(map(partial(_type_checker, origin), self.types)):
            self.wrong_argument()
        return origin

class CTTyped(CTConverter):
    """Accepts value of specified data type(s)."""
    def __init__(self, *types: acaciact.CTDataType):
        super().__init__()
        self.types = types

    def crepr(self) -> str:
        return " / ".join(dt.name for dt in self.types)

    def cconvert(self, origin: acaciact.CTExpr):
        if not any(dt.is_typeof(origin) for dt in self.types):
            self.wrong_argument()
        return origin

class UTyped(UConverter):
    """Accepts value of specified data type."""
    def __init__(self, rtype: _TYPED_TYPE, ctype: acaciact.CTDataType):
        super().__init__()
        self.rtype = rtype
        self.ctype = ctype

    def get_show_name(self) -> str:
        return _type_to_str(self.rtype)

    def uconvert(self, origin: _EXPR_T):
        if isinstance(origin, acaciact.CTObj):
            if not self.ctype.is_typeof(origin):
                self.wrong_argument()
        else:
            if not _type_checker(origin, self.rtype):
                self.wrong_argument()
        return origin

class UMultityped(UConverter):
    """Accepts value of several types."""
    def __init__(self, rtypes: Iterable[_TYPED_TYPE],
                 ctypes: Iterable[acaciact.CTDataType]):
        super().__init__()
        self.rtypes = tuple(rtypes)
        self.ctypes = tuple(ctypes)

    def get_show_name(self) -> str:
        return " / ".join(map(_type_to_str, self.rtypes))

    def uconvert(self, origin: _EXPR_T):
        if isinstance(origin, acaciact.CTObj):
            if not any(dt.is_typeof(origin) for dt in self.ctypes):
                self.wrong_argument()
        else:
            if not any(map(partial(_type_checker, origin), self.rtypes)):
                self.wrong_argument()
        return origin

class ConverterContainer(Converter, CTConverter):
    def __init_subclass__(subcls) -> None:
        orig_convert = subcls.convert
        orig_cconvert = subcls.cconvert
        def new_convert(self: ConverterContainer, origin: acacia.AcaciaExpr):
            if not all(isinstance(c, Converter) for c in self.__converters):
                raise ChopError('%r is used as runtime converter but not all '
                                'subconverters implement Converter')
            return orig_convert(self, origin)
        def new_cconvert(self: ConverterContainer, origin: acaciact.CTObj):
            if not all(isinstance(c, CTConverter) for c in self.__converters):
                raise ChopError('%r is used as compile time converter but not'
                                ' all subconverters implement CTConverter')
            return orig_cconvert(self, origin)
        subcls.convert = new_convert
        subcls.cconvert = new_cconvert

    def __init__(self, *converters: _CONVERTER_T):
        self.__converters = converters

    def crepr(self) -> str:
        return self.get_show_name()

def _convname(converter: _CONVERTER_T) -> str:
    if isinstance(converter, Converter):
        return converter.get_show_name()
    assert isinstance(converter, CTConverter)
    return converter.crepr()

def _exprrepr(expr: _EXPR_T) -> str:
    if isinstance(expr, acacia.AcaciaExpr):
        return str(expr.data_type)
    assert isinstance(expr, (acaciact.CTObj, acaciact.CTObjPtr))
    return expr.cdata_type.name

class LiteralInt(UTyped):
    """Accepts an integer literal and converts it to Python `int`.
    Default value should also be given as Python `int`.
    """
    def __init__(self):
        super().__init__(acacia.IntDataType, acacia.integer.ctdt_int)

    def get_show_name(self) -> str:
        return "int (literal)"

    def uconvert(self, origin) -> int:
        origin = super().uconvert(origin)
        if isinstance(origin, acacia.IntLiteral):
            return origin.value
        self.wrong_argument()

class LiteralFloat(UMultityped):
    """Accepts float and integer literal and converts it to Python
    `float`. Default value should also be given as Python `float`.
    """
    def __init__(self):
        super().__init__(
            (acacia.IntDataType, acacia.FloatDataType),
            (acacia.integer.ctdt_int, acacia.float_.ctdt_float)
        )

    def get_show_name(self) -> str:
        return "float (accepts int literal)"

    def uconvert(self, origin) -> float:
        origin = super().uconvert(origin)
        if isinstance(origin, acacia.IntLiteral):
            return float(origin.value)
        elif isinstance(origin, acacia.Float):
            return origin.value
        self.wrong_argument()

class LiteralString(UTyped):
    """Accepts a string literal and converts it to Python `str`.
    Default value should also be given as Python `str`.
    """
    def __init__(self):
        super().__init__(acacia.StringDataType, acacia.string.ctdt_string)

    def uconvert(self, origin) -> str:
        origin = super().uconvert(origin)
        assert isinstance(origin, acacia.String)
        return origin.value

class LiteralBool(UTyped):
    """Accepts a boolean literal and converts it to Python `bool`.
    Default value should also be given as Python `bool`.
    """
    def __init__(self):
        super().__init__(acacia.BoolDataType, acacia.boolean.ctdt_bool)

    def get_show_name(self) -> str:
        return "bool (literal)"

    def uconvert(self, origin) -> bool:
        origin = super().uconvert(origin)
        if isinstance(origin, acacia.BoolLiteral):
            return origin.value
        self.wrong_argument()

class Nullable(ConverterContainer):
    """Accepts "None" value and convert it to Python "None".
    Default value can be set to None.
    """
    def __init__(self, converter: _CONVERTER_T):
        super().__init__(converter)
        self.converter = converter

    def get_show_name(self) -> str:
        return _convname(self.converter) + " (or None)"

    def convert(self, origin: acacia.AcaciaExpr):
        if origin.data_type.matches_cls(acacia.NoneDataType):
            return None
        return self.converter.convert(origin)

    def cconvert(self, origin: acaciact.CTObj):
        if isinstance(origin, acacia.NoneLiteral):
            return None
        return self.converter.cconvert(origin)

class AnyOf(ConverterContainer):
    """Accepts arguments of several kinds."""
    def __init__(self, *converters: _CONVERTER_T):
        super().__init__(*converters)
        if not converters:
            raise ChopError("at least 1 converter needs to be specified")
        self.converters: List[_CONVERTER_T] = []
        for converter in converters:
            if isinstance(converter, AnyOf):
                self.converters.extend(converter.converters)
            else:
                self.converters.append(converter)

    def get_show_name(self) -> str:
        return " / ".join(_convname(c) for c in self.converters)

    def convert(self, origin: acacia.AcaciaExpr):
        for converter in self.converters:
            try:
                res = converter.convert(origin)
            except _WrongArgTypeError:
                pass
            else:
                return res
        else:
            self.wrong_argument()

    def cconvert(self, origin: acaciact.CTObj):
        for converter in self.converters:
            try:
                res = converter.cconvert(origin)
            except _WrongArgTypeError:
                pass
            else:
                return res
        else:
            self.wrong_argument()

class Iterator(Converter):
    """Accepts an Acacia iterable and converts it to Python list."""
    def get_show_name(self) -> str:
        return "(iterable)"

    def convert(self, origin: acacia.AcaciaExpr) -> "acacia.ITERLIST_T":
        try:
            res = origin.iterate()
        except NotImplementedError:
            self.wrong_argument()
        else:
            return res

class CTIterator(CTConverter):
    def crepr(self) -> str:
        return "(iterable)"

    def cconvert(self, origin: acaciact.CTExpr) -> List[acaciact.CTExpr]:
        try:
            res = abs(origin).citerate()
        except TypeError:
            self.wrong_argument()
        else:
            return res

class Selector(Multityped):
    """Accepts entity or Engroup and convert it to `MCSelector`."""
    def __init__(self):
        super().__init__((acacia.EntityDataType, acacia.EGroupDataType))

    def convert(self, origin: acacia.AcaciaExpr) -> "MCSelector":
        # Both `_EntityBase` and `EntityGroup` define `get_selector`.
        origin = super().convert(origin)
        return origin.get_selector()

class LiteralIntEnum(LiteralInt):
    """Accepts several specific integer literals values and converts
    input to Python `int`.
    """
    def __init__(self, *accepts: int):
        super().__init__()
        self.accepts = accepts

    def get_show_name(self) -> str:
        return (super().get_show_name()
                + " (one of %s)" % ", ".join(map(str, self.accepts)))

    def uconvert(self, origin) -> int:
        origin_int = super().uconvert(origin)
        if origin_int not in self.accepts:
            self.wrong_argument()
        return origin_int

class LiteralStringEnum(LiteralString):
    """Accepts several specific string literals values and converts
    input to Python `str`.
    """
    def __init__(self, *accepts: str):
        super().__init__()
        self.accepts = accepts

    def get_show_name(self) -> str:
        return (super().get_show_name()
                + " (one of %s)" % ", ".join(map(repr, self.accepts)))

    def uconvert(self, origin) -> str:
        origin_str = super().uconvert(origin)
        if origin_str not in self.accepts:
            self.wrong_argument()
        return origin_str

class ListOf(Typed):
    """Accepts a list of specified data type and converts it to Python
    `list`.
    """
    def __init__(self, converter: Converter):
        super().__init__(acacia.ListDataType)
        self.converter = converter

    def get_show_name(self) -> str:
        return "list of " + self.converter.get_show_name()

    def convert(self, origin: acacia.AcaciaExpr) -> list:
        origin = super().convert(origin)
        assert isinstance(origin, acacia.AcaciaList)
        return list(map(self.converter.convert, origin.items))

class CTListOf(CTTyped):
    def __init__(self, converter: CTConverter):
        super().__init__(acacia.list_.ctdt_constlist)
        self.converter = converter

    def get_show_name(self) -> str:
        return "list of " + self.converter.crepr()

    def cconvert(self, origin: acaciact.CTExpr) -> list:
        origin = abs(super().cconvert(origin))
        assert isinstance(origin, acacia.CTConstList)
        return list(map(self.converter.cconvert, origin.ptrs))

class MapOf(Typed):
    """Accepts a map of specified data type as key and value and
    converts it to Python `dict`.
    """
    def __init__(self, key: Converter, value: Converter):
        super().__init__(acacia.MapDataType)
        self.key = key
        self.value = value

    def get_show_name(self) -> str:
        return "map (%s: %s)" % (self.key.get_show_name(),
                                 self.value.get_show_name())

    def convert(self, origin: acacia.AcaciaExpr) -> dict:
        origin = super().convert(origin)
        assert isinstance(origin, acacia.Map)
        return {
            self.key.convert(key): self.value.convert(value)
            for key, value in origin.items()
        }

class CTMapOf(CTTyped):
    def __init__(self, key: CTConverter, value: CTConverter):
        super().__init__(acacia.map_.ctdt_constmap)
        self.key = key
        self.value = value

    def get_show_name(self) -> str:
        return "map (%s: %s)" % (self.key.crepr(), self.value.crepr())

    def cconvert(self, origin: acacia.AcaciaExpr) -> dict:
        origin = abs(super().cconvert(origin))
        assert isinstance(origin, acacia.CTConstMap)
        return {
            self.key.cconvert(key): self.value.cconvert(value)
            for key, value in origin.items()
        }

class PlayerSelector(Selector):
    """Accepts an entity or Engroup with player type and converts it
    to `MCSelector`.
    """
    def get_show_name(self) -> str:
        return super().get_show_name() + " (player type)"

    def convert(self, origin: acacia.AcaciaExpr) -> "MCSelector":
        selector = super().convert(origin)
        try:
            selector.player_type()
        except ValueError:
            self.wrong_argument()
        return selector

class RangedLiteralInt(LiteralInt):
    """Accepts a literal integer between given range and converts it to
    Python `int`.
    """
    def __init__(self, min_: Optional[int], max_: Optional[int]):
        super().__init__()
        if min_ is None:
            min_ = -float("inf")
        if max_ is None:
            max_ = float("inf")
        self.min = min_
        self.max = max_

    def get_show_name(self) -> str:
        return super().get_show_name() + " (%s ~ %s)" % (self.min, self.max)

    def uconvert(self, origin) -> int:
        num = super().uconvert(origin)
        if not self.min <= num <= self.max:
            self.wrong_argument()
        return num

class Callable(Converter):
    """Accepts a callable Acacia expression."""
    def get_show_name(self) -> str:
        return "(callable)"

    def convert(self, origin: acacia.AcaciaExpr) -> acacia.AcaciaCallable:
        if not isinstance(origin, acacia.AcaciaCallable):
            self.wrong_argument()
        return origin

class PosXZ(LiteralFloat):
    """
    Accepts a literal float or int and converts it to Python `float`.
    If the value is an integer, it gets `0.5` added to it.
    This is used for x and z axis in absolute position, as Minecraft
    also does this (move the position to block center).
    """
    def uconvert(self, origin) -> float:
        res = super().uconvert(origin)
        if isinstance(origin, acacia.IntLiteral):
            res += 0.5
        return res

class CTReference(CTConverter):
    def crepr(self) -> str:
        return "(reference)"

    def cconvert(self, origin: acaciact.CTExpr):
        if not isinstance(origin, acaciact.CTObjPtr):
            self.wrong_argument()
        return origin

### Parser

def _check_repeat(names: List[str], renames: List[str]):
    got = set()
    for name in names:
        if name in got:
            raise ChopError("repeated argument %r" % name)
        got.add(name)
    got = set()
    for name in renames:
        if name in got:
            raise ChopError("repeated argument rename %r" % name)
        got.add(name)

def _call_impl(implementation, all_args: List[str], *args, **kwds):
    try:
        return implementation(*args, **kwds)
    except ArgumentError as err:
        if err.arg not in all_args:
            # Make sure `err.arg` is a valid argument name
            raise ChopError("unknown argument %r" % err.arg)
        else:
            raise AcaciaError(ErrorType.INVALID_BIN_FUNC_ARG,
                              arg=err.arg, message=err.message)

def _get_convert(origin: _EXPR_T, converter: _CONVERTER_T):
    if isinstance(origin, acacia.AcaciaExpr):
        if isinstance(converter, Converter):
            convert = lambda: converter.convert(origin)
        elif isinstance(origin, acacia.ConstExpr):
            convert = lambda: converter.cconvert(origin.to_ctexpr())
        else:
            raise _PreconvertError(_PE_NOT_CONST)
    else:
        if isinstance(converter, CTConverter):
            convert = lambda: converter.cconvert(origin)
        else:
            try:
                origin_rt = abs(origin).to_rt()
            except TypeError:
                raise _PreconvertError(_PE_NOT_RT)
            convert = lambda: converter.convert(origin_rt)
    return convert

class _Chopper:
    def __init__(self, building: _BuildingParser):
        self.pos_only: List[_Argument] = []
        self.pos_n_kw: List[_Argument] = []
        self.kw_only: List[_Argument] = []
        self.args: Optional[_ArgumentList] = None
        self.kwds: Optional[_ArgumentList] = None
        self.implementation = building.get_target()
        # Parse builder stack
        got_slash = False
        got_star = False
        got_kwds = False
        got_default = False
        before_slash = []
        for type_, definition in building:
            if type_ == _BP_SLASH:
                if got_slash or got_star or got_kwds:
                    raise ChopError("only arguments can go before axe.slash")
                got_slash = True
            elif type_ == _BP_STAR or type_ == _BP_STAR_ARG:
                if got_star or got_kwds:
                    raise ChopError("only arguments or axe.slash can go "
                                    "before axe.star or axe.star_arg")
                if type_ == _BP_STAR_ARG:
                    self.args = definition
                got_star = True
            elif type_ == _BP_KWDS:
                if got_kwds:
                    raise ChopError("multiple axe.kwds")
                self.kwds = definition
                got_kwds = True
            else:
                assert type_ == _BP_ARG and isinstance(definition, _Argument)
                if got_kwds:
                    raise ChopError("argument after axe.kwds")
                if definition.has_default():
                    got_default = True
                else:
                    if got_default:
                        raise ChopError("non-default argument follows "
                                        "default argument")
                if got_star:
                    self.kw_only.append(definition)
                else:
                    if got_slash:
                        self.pos_n_kw.append(definition)
                    else:
                        before_slash.append(definition)
        if got_slash:
            self.pos_only.extend(before_slash)
        else:
            self.pos_n_kw.extend(before_slash)

        names, renames = [], []
        for arg_def in chain(self.pos_only, self.pos_n_kw, self.kw_only):
            names.append(arg_def.name)
            renames.append(arg_def.rename)
        if self.args:
            names.append(self.args.name)
            renames.append(self.args.rename)
        if self.kwds:
            names.append(self.kwds.name)
            renames.append(self.kwds.rename)
        _check_repeat(names, renames)

        self.MAX_POS_ARG = len(self.pos_only) + len(self.pos_n_kw)
        self.pos_only_names = [arg_def.name for arg_def in self.pos_only]
        self.kw_name2def = {arg_def.name: arg_def
                            for arg_def in chain(self.kw_only, self.pos_n_kw)}

    def _convert(self, origin: _EXPR_T, converter: _CONVERTER_T, arg: str):
        try:
            convert = _get_convert(origin, converter)
        except _PreconvertError as err:
            raise AcaciaError(ErrorType.ANY, message=err.show(arg))
        try:
            return convert()
        except _WrongArgTypeError:
            raise AcaciaError(
                ErrorType.WRONG_ARG_TYPE,
                expect=_convname(converter), arg=arg,
                got=_exprrepr(origin)
            )

    def __call__(self, compiler: "Compiler", args: List[_EXPR_T],
                 kwds: Dict[str, _EXPR_T]):
        res: Dict[str, Any] = {}
        arg_got: List[str] = []
        # Positional arguments
        if len(args) > self.MAX_POS_ARG:
            if self.args is None:
                raise AcaciaError(ErrorType.TOO_MANY_ARGS)
            else:
                res[self.args.rename] = [
                    self._convert(
                        arg, self.args.converter,
                        "#%d(*%s)" % (i, self.args.name)
                    )
                    for i, arg in enumerate(
                        args[self.MAX_POS_ARG:], start=self.MAX_POS_ARG + 1
                    )
                ]
                arg_got.append(self.args.name)
        for arg_def, arg in zip(chain(self.pos_only, self.pos_n_kw), args):
            res[arg_def.rename] = self._convert(
                arg, arg_def.converter, arg_def.name
            )
            arg_got.append(arg_def.name)
        # Keyword arguments
        extra_kwds = {}
        for arg_name, arg in kwds.items():
            if arg_name in self.pos_only_names:
                raise AcaciaError(
                    ErrorType.ANY,
                    message='Position-only argument "%s" passed as keyword'
                            % arg_name
                )
            if arg_name not in self.kw_name2def:
                if self.kwds is None:
                    raise AcaciaError(ErrorType.UNEXPECTED_KEYWORD_ARG,
                                      arg=arg_name)
                else:
                    extra_kwds[arg_name] = arg
                    continue
            if arg_name in arg_got:
                raise AcaciaError(ErrorType.ARG_MULTIPLE_VALUES, arg=arg_name)
            arg_def = self.kw_name2def[arg_name]
            res[arg_def.rename] = self._convert(
                arg, arg_def.converter, arg_def.name
            )
            arg_got.append(arg_name)
        if extra_kwds:
            assert self.kwds
            res[self.kwds.rename] = {
                arg_name: self._convert(
                    arg, self.kwds.converter,
                    "%s(**%s)" % (arg_name, self.kwds.name)
                )
                for arg_name, arg in extra_kwds.items()
            }
            arg_got.append(self.kwds.name)
        # Check for missing arguments and fix with default values
        for arg_def in chain(self.pos_only, self.pos_n_kw, self.kw_only):
            if arg_def.name not in arg_got:
                try:
                    default = arg_def.get_default()
                except ValueError:
                    raise AcaciaError(ErrorType.MISSING_ARG, arg=arg_def.name)
                else:
                    res[arg_def.rename] = default
                    arg_got.append(arg_def.name)
        if self.args and self.args.name not in arg_got:
            res[self.args.rename] = []
            arg_got.append(self.args.name)
        if self.kwds and self.kwds.name not in arg_got:
            res[self.kwds.rename] = {}
            arg_got.append(self.kwds.name)
        return _call_impl(self.implementation, arg_got, compiler, **res)

def _create_signature(arg_defs: List[_Argument]) -> str:
    return "(%s)" % ", ".join(
        "%s: %s" % (
            arg_def.name,
            _convname(arg_def.converter)
        )
        for arg_def in arg_defs
    )

class _OverloadImplWrapper:
    def __init__(self, method: PyCallable, building: _BuildingParser,
                 version: Optional["VersionRequirement"]):
        self.method = method
        self.building = building
        self.version = version

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return self.method(*args, **kwds)

class _OverloadMethod(classmethod):
    def __init__(self, building: _BuildingParser,
                 version: Optional["VersionRequirement"] = None):
        super().__init__(building.get_target())
        self.building = building
        self.version = version

    def __get__(self, instance, owner: Optional[type] = None) -> PyCallable:
        return _OverloadImplWrapper(
            super().__get__(instance, owner), self.building, self.version
        )

### Parser Interface

@_parser_component
def chop(building: _BuildingParser):
    """Use a Python-style argument parser for decorated function.
    Example:
    >>> @chop
    ... @arg("foo", Nullable(Typed(acacia.BoolDataType)))
    ... @arg("bar", LiteralInt(), default=11)
    ... def f(compiler, foo, bar):
    ...     # implement this binary function here
    ...     print(foo, bar)
    ...     return acacia.NoneVar(compiler)
    >>> func = acacia.BinaryFunction(f, compiler=compiler)
    >>> func.call(
    ...     [], {"foo": acacia.BoolLiteral(True, compiler),
    ...          "bar": acacia.IntLiteral(2, compiler)}
    ... )
    <acacia.BoolLiteral object at ...> 2
    >>> func.call(
    ...     [acacia.NoneLiteral(compiler)], {}
    ... )
    None 11
    """
    return _Chopper(building)

class OverloadChopped(type):
    """Implement a binary function with overload-style argument parser.
    Example:
    >>> class Foo(metaclass=OverloadChopped):
    ...     @overload
    ...     @arg("a", acacia.BoolDataType)
    ...     @arg("b", LiteralInt())
    ...     def f1(cls, compiler, a, b):
    ...         print("f1: ", a, b)
    ...         return acacia.NoneVar(compiler)
    ...     @overload
    ...     @arg("a", acacia.BoolDataType)
    ...     def f2(cls, compiler, a):
    ...         print("f2: ", a)
    ...         return cls.f1(compiler, a, b=10)
    >>> func = acacia.BinaryFunction(Foo, compiler)
    >>> func.call(
    ...     [acacia.BoolLiteral(True, compiler)], {}
    ... )
    f2: <acacia.BoolLiteral object at ...>
    f1: <acacia.BoolLiteral object at ...> 10
    >>> func.call(
    ...     [acacia.BoolLiteral(False, compiler),
    ...      acacia.IntLiteral(5, compiler)], {}
    ... )
    f1: <acacia.BoolLiteral object at ...> 5
    """

    # For IDE hint only:
    __overloads: List[Tuple[_OverloadImplWrapper, List[_Argument]]]

    def __new__(meta_cls, cls_name, bases, attributes):
        cls = type.__new__(meta_cls, cls_name, bases, attributes)
        # Parse the class
        impls = [attr for _, attr in inspect.getmembers(cls)
                 if isinstance(attr, _OverloadImplWrapper)]
        cls.__overloads = []
        for impl in impls:
            building = impl.building
            if any(type_ != _BP_ARG for type_, _ in building):
                raise ChopError("only arguments are allowed in overload "
                                "definitions")
            arg_defs: List[_Argument] = [arg_def for _, arg_def in building]
            if any(arg_def.has_default() for arg_def in arg_defs):
                raise ChopError("overload arguments can't have default values")
            cls.__overloads.append((impl, arg_defs))
            _check_repeat([arg_def.name for arg_def in arg_defs],
                          [arg_def.rename for arg_def in arg_defs])
        return cls

    @staticmethod
    def _format_version(version: Optional["VersionRequirement"]):
        if version is None:
            return ""
        else:
            return " [MC %s]" % version.to_str()

    def __call__(self, compiler: "Compiler", args: List[_EXPR_T],
                 kwds: Dict[str, _EXPR_T]):
        if kwds:
            raise AcaciaError(ErrorType.ANY,
                              message="Overload functions don't support "
                                      "keyword arguments")
        L = len(args)
        for implementation, arg_defs in self.__overloads:
            if len(arg_defs) != L:
                continue
            version = implementation.version
            if version and not version.validate(compiler.cfg.mc_version):
                continue
            res = {}
            for arg_def, arg in zip(arg_defs, args):
                try:
                    convert = _get_convert(arg, arg_def.converter)
                except _PreconvertError:
                    break
                try:
                    converted = convert()
                except _WrongArgTypeError:
                    break
                res[arg_def.rename] = converted
            else:
                return _call_impl(
                    implementation,
                    [arg_def.name for arg_def in arg_defs],
                    compiler, **res
                )
        else:
            raise AcaciaError(
                ErrorType.ANY,
                message="No overload matches given arguments: "
                        "got %s, expected %s" % (
                    "(%s)" % ", ".join(_exprrepr(arg) for arg in args),
                    " / ".join(
                        "%s%s" % (
                            _create_signature(arg_defs),
                            self._format_version(impl.version)
                        )
                        for impl, arg_defs in self.__overloads
                    )
                )
            )

@_parser_component
def overload(building: _BuildingParser):
    """Start an overload implementation in a class decorated with
    metaclass `OverloadChopped`. The decorated implementation will be
    made a `classmethod`.
    """
    return _OverloadMethod(building)

def overload_versioned(version: "VersionRequirement"):
    """Return a decorator that is same as @overload, but decorated
    implementation will only be available when compiler.cfg.mc_version
    satifies given requirements.
    """
    @_parser_component
    def _decorator(building: _BuildingParser):
        return _OverloadMethod(building, version)
    return _decorator
