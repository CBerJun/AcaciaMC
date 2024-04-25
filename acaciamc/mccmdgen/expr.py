"""Base stuffs for generating codes of Acacia expressions."""

__all__ = [
    # Base classes
    'AcaciaExpr', 'VarValue', 'AcaciaCallable',
    'ConstExpr', 'ConstExprCombined',
    # Type checking
    'ARGS_T', 'KEYWORDS_T', 'CALLRET_T', 'ITERLIST_T', 'CMDLIST_T',
]

from typing import List, Union, Dict, Tuple, Hashable, Optional, TYPE_CHECKING
from abc import ABCMeta, abstractmethod

from acaciamc.mccmdgen.symbol import SymbolTable
from acaciamc.error import *
from acaciamc.mccmdgen.ctexpr import CTObj

if TYPE_CHECKING:
    from types import NotImplementedType  # Python 3.10
    from acaciamc.ast import Operator
    from acaciamc.mccmdgen.datatype import DataType
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.cmds import Command
    from acaciamc.mccmdgen.ctexpr import CTExpr
    from acaciamc.objects.boolean import CompareBase

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
     - add, sub, mul, div, mod: represents binary +, -, *, /, %,
       respectively. There are also radd, rsub, rmul, rdiv, rmod,
       which are similar to those in Python.
     - unarypos, unaryneg, unarynot: represents unary +, - and "not",
       respectively.
     - iadd, isub, imul, idiv, imod: represents +=, -=, *=, /=, %=
       respectively.
    When you are not satisfied with input operand type, please raise
    `TypeError`.
    """
    def __init__(self, type_: "DataType", compiler: "Compiler"):
        super().__init__()
        self.compiler = compiler
        self.data_type = type_
        self.attribute_table = SymbolTable()

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

    def hash(self) -> Hashable:
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

    def add(self, other: "AcaciaExpr") -> "AcaciaExpr":
        raise TypeError
    def sub(self, other: "AcaciaExpr") -> "AcaciaExpr":
        raise TypeError
    def mul(self, other: "AcaciaExpr") -> "AcaciaExpr":
        raise TypeError
    def div(self, other: "AcaciaExpr") -> "AcaciaExpr":
        raise TypeError
    def mod(self, other: "AcaciaExpr") -> "AcaciaExpr":
        raise TypeError

    def radd(self, other: "AcaciaExpr") -> "AcaciaExpr":
        raise TypeError
    def rsub(self, other: "AcaciaExpr") -> "AcaciaExpr":
        raise TypeError
    def rmul(self, other: "AcaciaExpr") -> "AcaciaExpr":
        raise TypeError
    def rdiv(self, other: "AcaciaExpr") -> "AcaciaExpr":
        raise TypeError
    def rmod(self, other: "AcaciaExpr") -> "AcaciaExpr":
        raise TypeError

    def unarypos(self) -> "AcaciaExpr":
        raise TypeError
    def unaryneg(self) -> "AcaciaExpr":
        raise TypeError
    def unarynot(self) -> "AcaciaExpr":
        raise TypeError

class ConstExpr(AcaciaExpr, metaclass=ABCMeta):
    @abstractmethod
    def to_ctexpr(self) -> "CTExpr":
        pass

class VarValue(AcaciaExpr):
    """
    `VarValue`s are special `AcaciaExpr`s that can be assigned to. It
    represents a "variable" of a storable type and is sometimes used as
    a temporary (with `is_temporary` set to `True`, in which case it
    cannot be assigned).
    e.g. 1 + 2 -> IntLiteral(3) -> Unassignable
    e.g. a -> IntVar(ScbSlot("acacia3", "acacia")) -> Assignable
    e.g. scb("x", "scb") -> IntVar(ScbSlot("x", "scb")) -> Assignable
    e.g. bool -> Type -> Unassignable
    """
    is_temporary = False  # used as a temporary and is read-only

    def swap(self, other: "VarValue") -> CMDLIST_T:
        raise NotImplementedError

    def is_assignable(self) -> bool:
        return not self.is_temporary

class AcaciaCallable(AcaciaExpr, metaclass=ABCMeta):
    """Acacia expressions that are callable."""
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self.source: Optional[SourceLocation] = None
        self.func_repr = "<unknown>"

    def call_withframe(
            self, args: ARGS_T, keywords: KEYWORDS_T,
            location: Optional[Union[SourceLocation, str]] = None
        ) -> CALLRET_T:
        """
        Call this expression, and add this to error frame if an error
        occurs.
        """
        return traced_call(
            self.call, location, self.source, self.func_repr,
            args, keywords
        )

    @abstractmethod
    def call(self, args: ARGS_T, keywords: KEYWORDS_T) -> CALLRET_T:
        """
        Call this expression.
        Return value:
         1st element: Result of this call
         2nd element: Commands to run
        """
        pass

class ConstExprCombined(ConstExpr, CTObj):
    def __init_subclass__(cls) -> None:
        for meth in (
            'add', 'sub', 'mul', 'div', 'mod',
            'radd', 'rsub', 'rmul', 'rdiv', 'rmod',
            'unarypos', 'unaryneg', 'unarynot', 'hash'
        ):
            cmeth = f"c{meth}"
            func = getattr(cls, cmeth)
            deffunc = getattr(CTObj, cmeth)
            if func is not deffunc:
                setattr(cls, meth, func)

    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self.attributes = self.attribute_table

    def to_ctexpr(self):
        return self

    def to_rt(self):
        return self

    def cmdstr(self):
        try:
            return self.cstringify()
        except TypeError:
            raise NotImplementedError

    def compare(self, op: "Operator", other: AcaciaExpr):
        try:
            b = self.ccompare(op, other)
        except TypeError:
            return NotImplemented
        if isinstance(b, bool):
            from acaciamc.objects.boolean import BoolLiteral
            return BoolLiteral(b, self.compiler)
        return b
