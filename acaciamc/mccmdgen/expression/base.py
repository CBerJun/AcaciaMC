"""Base stuffs for generating codes of Acacia expressions."""

__all__ = [
    # Base classes
    'AcaciaExpr', 'VarValue', 'AcaciaCallable', 'ConstExpr', 'CTCallable',
    # Utils
    'ArgumentHandler', 'ImmutableMixin', 'transform_immutable',
    # Type checking
    'ARGS_T', 'KEYWORDS_T', 'CALLRET_T', 'ITERLIST_T', 'CMDLIST_T',
]

from typing import (
    List, Union, Dict, Tuple, Callable, Hashable, Optional, TYPE_CHECKING
)
from abc import ABCMeta, abstractmethod

from acaciamc.mccmdgen.symbol import AttributeTable
from acaciamc.error import *

if TYPE_CHECKING:
    from types import NotImplementedType  # Python 3.10
    from acaciamc.ast import Operator
    from acaciamc.mccmdgen.datatype import DataType
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.cmds import Command
    from .boolean import CompareBase

ARGS_T = List["AcaciaExpr"]  # Positional arguments
KEYWORDS_T = Dict[str, "AcaciaExpr"]  # Keyword arguments
CMDLIST_T = List[Union[str, "Command"]]
CALLRET_T = Tuple["AcaciaExpr", CMDLIST_T]  # Result
ITERLIST_T = List["AcaciaExpr"]

class AcaciaExpr:
    """Base class for EVERYTHING that represents an Acacia expression.
    NOTE Contributer Guide:
    There are 2 types of Acacia data types:
    - The "storable" types. These types of expressions are stored in
      Minecraft, and their values can be changed when running the code
      (since it is stored in MC).
      e.g. int, bool
    - The "unstorable" types. These types of expression cannot be stored
      in Minecraft, and is only tracked by the compiler. Therefore,
      their values can't be changed.
      e.g. str, module, function
    To define a new type, you need to:
     - Define a subclass of `DataType` that represents this type.
       To implement a simple type, just subclass `DefaultDataType`, in
       which you just need to specify `name` attribute.
     - Define at least one subclass of `AcaciaExpr`, which represents
       the objects of this type.
       To make your object callable in Acacia, subclass `AcaciaCallable`
       and implement `call` method.
       `cmdstr` is a special method that returns the string
       representation of this expression used in raw command
       substitution.
    Extra things for "storable" types to implement:
     - at least one (usually 1) class that is a subclass of `VarValue`,
       to represent this kind of value that is stored in Minecraft.
     - `export` method, called when user assigns the value of this
       expression to a `VarValue` of same type.
     - the class that defines this type (subclass of `DataType`) should
       subclass `Storable`. It will have to implement `new_var` method,
       to allow creating a new `VarValue` of this type.
    Take builtin "int" as an example:
     - `IntVar`, which holds a Minecraft score, is implemented.
     - All the AcaciaExprs of `int` type implements `export`.
     - `IntDataType` does have a `new_var` method, which creates a new
       `IntVar`.

    To implement operator for your type, here are some methods:
     - __add__, __sub__, __mul__, __floordiv__, __mod__: represents
       binary +, -, *, /, %, respectively. See also __radd__,
       __rsub__, etc.
     - __pos__, __neg__, not_: represents unary +, - and "not",
       respectively.
     - iadd, isub, imul, idiv, imod: represents +=, -=, *=, /=, %=
       respectively.
    When you are not satisfied with input operand type, please raise
    `TypeError`, EXCEPT for binary operators (return `NotImplemented`
    instead).
    """
    def __init__(self, type_: "DataType", compiler: "Compiler"):
        self.compiler = compiler
        self.data_type = type_
        self.attribute_table = AttributeTable()

    def is_assignable(self) -> bool:
        """Return whether this expression is a lvalue at runtime."""
        return False

    def export(self, var: "VarValue") -> CMDLIST_T:
        """Return the commands that assigns value of `self` to `var`.
        Since we need a `VarValue` here, only "storable" types need
        to implement this.
        """
        raise NotImplementedError

    def cmdstr(self) -> str:
        """Return a string representation of this expression, used in
        raw commands. If not implemented, then the object can not be
        formatted in a command.
        """
        raise NotImplementedError

    def iterate(self) -> ITERLIST_T:
        """Implements for-in iteration. Should return an iterable
        of `AcaciaExpr`, in which values are bound to "for" variable
        one by one. If not implemented, then the object can't be
        iterated in a for-in structure.
        NOTE that for-in on an entity group is handled completely
        differently by the generator, so it should never implement this.
        """
        raise NotImplementedError

    def datatype_hook(self) -> "DataType":
        """When this expression is used as a type specifier, this
        method is called to obtain the `DataType`.
        """
        raise NotImplementedError

    def map_hash(self) -> Hashable:
        """When this expression is used as a map's key, this method
        is called to obtain the hash value.
        """
        raise NotImplementedError

    def compare(self, op: "Operator", other: "AcaciaExpr") \
            -> Union["CompareBase", "NotImplementedType"]:
        """
        Implement comparison operators for this expression.
        Return value should either be `NotImplemented` or an
        `AcaciaExpr` with boolean type.
        """
        return NotImplemented

class ArgumentHandler:
    """A tool to match function arguments against a given definition."""
    def __init__(self, args: List[str], arg_types: Dict[str, "DataType"],
                 arg_defaults: Dict[str, Union[AcaciaExpr, None]]):
        """`args`, `arg_types` and `arg_defaults` decide the expected
        pattern.
        """
        self.args = args
        self.arg_types = arg_types
        self.arg_defaults = arg_defaults
        # Throw away arguments that have no default value in
        # `arg_defaults`.
        for arg, value in self.arg_defaults.copy().items():
            if value is None:
                del self.arg_defaults[arg]
        self.ARG_LEN = len(self.args)

    def match(self, args: ARGS_T,
              keywords: KEYWORDS_T) -> Dict[str, AcaciaExpr]:
        """Match the expected pattern with given call arguments.
        Return a `dict` mapping names to argument value.
        """
        if len(args) > self.ARG_LEN:
            raise Error(ErrorType.TOO_MANY_ARGS)
        res = dict.fromkeys(self.args)
        # util
        def _check_arg_type(arg: str, value: AcaciaExpr):
            # check if `arg` got the correct type of `value`
            t = self.arg_types[arg]
            if (t is not None) and (not t.matches(value.data_type)):
                raise Error(
                    ErrorType.WRONG_ARG_TYPE, arg=arg,
                    expect=str(t), got=str(value.data_type)
                )
        # positioned
        for i, value in enumerate(args):
            arg = self.args[i]
            _check_arg_type(arg, value)
            res[arg] = value
        # keyword
        for arg, value in keywords.items():
            # check multiple values of the same var
            if arg not in self.args:
                raise Error(ErrorType.UNEXPECTED_KEYWORD_ARG, arg=arg)
            if res[arg] is not None:
                raise Error(ErrorType.ARG_MULTIPLE_VALUES, arg=arg)
            _check_arg_type(arg, value)
            res[arg] = value
        # if any args are missing use default if exists, else error
        for arg, value in res.copy().items():
            if value is None:
                if arg in self.arg_defaults:
                    res[arg] = self.arg_defaults[arg]
                else:
                    raise Error(ErrorType.MISSING_ARG, arg=arg)
        return res

class VarValue(AcaciaExpr):
    """
    `VarValue`s are special `AcaciaExpr`s that can be assigned to. It
    represents a "variable" of a storable type and is sometimes used as
    a temporary (with `is_temporary` set to `True`, in which case it
    cannot be assigned).
    e.g. 1 + 2 -> IntLiteral(3) -> Unassignable
    e.g. a -> IntVar("acacia", "acacia3") -> Assignable
    e.g. |"x": "y"| -> IntVar("y", "x") -> Assignable
    e.g. bool -> Type -> Unassignable
    """
    is_temporary = False  # used as a temporary and is read-only

    def swap(self, other: "VarValue") -> CMDLIST_T:
        raise NotImplementedError

    def is_assignable(self) -> bool:
        return not self.is_temporary

class _CallableBase(AcaciaExpr):
    def __init__(self, type_: "DataType", compiler: "Compiler"):
        super().__init__(type_, compiler)
        self.source = SourceLocation()
        self.func_repr = "<unknown>"

    def _wrap_frame(
            self, call: Callable, args: ARGS_T, keywords: KEYWORDS_T,
            location: Optional[Union[SourceLocation, str]] = None
        ):
        try:
            return call(args, keywords)
        except Error as err:
            if location is None:
                location = SourceLocation()
            elif isinstance(location, str):
                location = SourceLocation(file=location)
            if self.source.file_set():
                note = "Callee defined at %s" % self.source
            else:
                note = None
            err.add_frame(ErrFrame(
                location, "Calling %s" % self.func_repr, note
            ))
            raise

class AcaciaCallable(_CallableBase, metaclass=ABCMeta):
    """Acacia expressions that are callable."""
    def call_withframe(
            self, args: ARGS_T, keywords: KEYWORDS_T,
            location: Optional[Union[SourceLocation, str]] = None
        ) -> CALLRET_T:
        """
        Call this expression, and add this to error frame if an error
        occurs.
        """
        return self._wrap_frame(self.call, args, keywords, location)

    @abstractmethod
    def call(self, args: ARGS_T, keywords: KEYWORDS_T) -> CALLRET_T:
        """
        Call this expression.
        Return value:
         1st element: Result of this call
         2nd element: Commands to run
        """
        pass

class ConstExpr(AcaciaExpr, metaclass=ABCMeta):
    """An expression known and only available at compile time."""
    pass

class CTCallable(ConstExpr, _CallableBase, metaclass=ABCMeta):
    @abstractmethod
    def ccall(self, args: ARGS_T, keywords: KEYWORDS_T) -> ConstExpr:
        """Call inside const context."""
        pass

    def ccall_withframe(
            self, args: ARGS_T, keywords: KEYWORDS_T,
            location: Optional[Union[SourceLocation, str]] = None
        ) -> ConstExpr:
        """
        Call this expression (in const context), and add this to error
        frame if an error occurs.
        """
        return self._wrap_frame(self.ccall, args, keywords, location)

class ImmutableMixin:
    """An `AcaciaExpr` that can't be changed and only allows
    transformations into another object of same type.
    """
    def copy(self) -> "ImmutableMixin":
        raise NotImplementedError

def transform_immutable(self: ImmutableMixin):
    """Return a decorator for binary function implementations that
    transforms an immutable expression to another one.
    """
    if not isinstance(self, ImmutableMixin):
        raise TypeError("can't transform non-ImmutableMixin")
    def _decorator(func: Callable):
        def _decorated(*args, **kwds):
            return func(self.copy(), *args, **kwds)
        return _decorated
    return _decorator
