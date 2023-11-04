"""Base stuffs for generating codes of Acacia expressions."""

__all__ = [
    # Base classes
    'AcaciaExpr', 'VarValue', 'AcaciaCallable', 'SupportsGetItem',
    'SupportsSetItem',
    # Utils
    'ArgumentHandler', 'export_need_tmp',
    'ImmutableMixin', 'transform_immutable',
    # Type checking
    'ARGS_T', 'KEYWORDS_T', 'CALLRET_T', 'ITERLIST_T', 'CMDLIST_T',
]

from typing import (
    List, Union, Dict, Tuple, Callable, Hashable, Optional, TYPE_CHECKING
)
from abc import ABCMeta, abstractmethod

from acaciamc.mccmdgen.datatype import Storable
from acaciamc.mccmdgen.symbol import AttributeTable
from acaciamc.error import *

if TYPE_CHECKING:
    from acaciamc.mccmdgen.datatype import DataType
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.cmds import Command

### --- UTILS --- ###

def export_need_tmp(new_tmp: Callable[["Compiler"], "VarValue"]):
    """Return a decorator for `AcaciaExpr.export`.
    Usually when we do `A.export(B)`, the value of `A` is dumped to
    `B` directly without a temporary value.
    This decorator add a temporary value `T`, first `A.export(T)`,
    then `T.export(B)`.
    This is to prevent changing the value of `B` too early.
    WITHOUT a temporary value, take `a = 1 + a` as an example,
    we let `a` = 1 first, and then plus `a` itself to it, which is 1
    now, so whatever `a` is before assigning, it becomes 2 now.
    `new_tmp` should return a temporary `VarValue` of the same data type
    as the class where this decorator is used.
    """
    def _decorator(func):
        def _decorated(self, var: VarValue):
            assert isinstance(self, AcaciaExpr)
            assert isinstance(self.data_type, Storable)
            temp = new_tmp(var.compiler)
            cmds = []
            cmds.extend(func(self, temp))
            cmds.extend(temp.export(var))
            return cmds
        return _decorated
    return _decorator

### --- END UTILS --- ###

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

    def export(self, var: "VarValue") -> CMDLIST_T:
        """Return the commands that assigns value of `self` to `var`.
        Since we need a `VarValue` here, only "storable" types need
        to implement this.
        The method can be decorated with `export_need_tmp`.
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
    """`VarValue`s are special `AcaciaExpr`s that can be assigned to.
    Examples are builtin int, bool and nonetype.
    Users can create new variables of these types.
    `VarValue`s are also used to hold temporary variables.
    e.g. 1 + 2 -> IntLiteral(3) -> Unassignable
    e.g. a -> IntVar("acacia", "acacia3") -> Assignable
    e.g. |"x": "y"| -> IntVar("y", "x") -> Assignable
    e.g. bool -> Type -> Unassignable
    """
    pass

class AcaciaCallable(AcaciaExpr, metaclass=ABCMeta):
    """Acacia expressions that are callable."""
    def __init__(self, type_: "DataType", compiler: "Compiler"):
        super().__init__(type_, compiler)
        self.source = SourceLocation()
        self.func_repr = "<unknown>"

    def call_withframe(
            self, args: ARGS_T, keywords: KEYWORDS_T,
            location: Optional[Union[SourceLocation, str]] = None
        ) -> CALLRET_T:
        """
        Call this expression, and add this to error frame if an error
        occurs.
        """
        try:
            return self.call(args, keywords)
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

    @abstractmethod
    def call(self, args: ARGS_T, keywords: KEYWORDS_T) -> CALLRET_T:
        """
        Call this expression.
        Return value:
         1st element: Result of this call
         2nd element: Commands to run
        """
        pass

class SupportsGetItem(AcaciaExpr, metaclass=ABCMeta):
    """Acacia expressions that can be subscripted and be a rvalue."""
    @abstractmethod
    def getitem(self, subscripts: Tuple[AcaciaExpr]) \
            -> Union[CALLRET_T, AcaciaExpr]:
        """Implements subscripting. Return value is same as `call`."""
        pass

class SupportsSetItem(AcaciaExpr, metaclass=ABCMeta):
    """Acacia expressions that can be subscripted and be a lvalue."""
    @abstractmethod
    def setitem(self, subscripts: Tuple[AcaciaExpr],
                value: AcaciaExpr) -> Optional[CMDLIST_T]:
        """Implements assignment. Return value is commands to run."""
        pass

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
