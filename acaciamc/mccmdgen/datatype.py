"""Acacia compiler's internal representation of types of expressions."""

__all__ = ['DataType', 'DefaultDataType', 'Storable', 'SupportsEntityField']

from typing import TYPE_CHECKING, Type as PythonType
from abc import ABCMeta, abstractmethod

# `import acaciamc.mccmdgen.expression as acaciaexpr` won't work in 3.6
# because of a Python bug (see https://bugs.python.org/issue23203)
from acaciamc.mccmdgen import expression as acaciaexpr
import acaciamc.tools as acaciatools

if TYPE_CHECKING:
    from acaciamc.mccmdgen.expression.entity import _EntityBase
    from acaciamc.mccmdgen.expression.base import (
        AcaciaExpr, VarValue, AcaciaCallable
    )
    from acaciamc.compiler import Compiler

class DataType(metaclass=ABCMeta):
    """Data type like `int`, `bool` or entity like `entity(Template)`.
    WHAT'S THE FIFFERENCE BETWEEN `Type` AND THIS?
     `Type` is JUST an expression that implements `datatype_hook` so it
     can be used as a type specifier by users. `DataType` is not an
     expression but an internal representation of expression type. It
     specifies the type of an expression including extra information
     like template for entity.
    """
    @abstractmethod
    def __str__(self) -> str:
        pass

    @classmethod
    @abstractmethod
    def name_no_generic(cls) -> str:
        pass

    @abstractmethod
    def matches(self, other: "DataType") -> bool:
        """Return whether `other` is compatible to be assigned to
        variables of this type. (i.e. if `other` is entity, check
        whether the template of `other` is a sub-template of this
        type's template).
        """
        pass

    def is_type_of(self, expr: "AcaciaExpr") -> bool:
        """Return whether `expr` is of this type."""
        return self.matches(expr.data_type)

    @classmethod
    def matches_cls(cls, other: PythonType["DataType"]) -> bool:
        return issubclass(other, cls)

class Storable(DataType):
    """A "storable" data type. (See `AcaciaExpr`)."""
    def __init__(self, compiler: "Compiler") -> None:
        super().__init__()
        self.compiler = compiler

    @abstractmethod
    def new_var(self) -> "VarValue":
        """New a `VarValue` of this type.
        Only "storable" types need to implement this.
        """
        pass

    def get_var_initializer(self, var: "VarValue") -> "AcaciaCallable":
        """Return a callable `AcaciaExpr` that accepts user arguments
        and initialize a `VarValue` of this type. Result of this
        callable should be Acacia "None" and commands may be added.
        `var` is the variable to initialize.
        """
        @acaciatools.axe.chop
        def _init(compiler):
            return None
        return acaciaexpr.BinaryFunction(_init, self.compiler)

class SupportsEntityField(DataType):
    """Data type that can be used as a field of an entity."""
    @abstractmethod
    def new_entity_field(self) -> dict:
        """When a field of an entity template is this type, this is
        called. This should return a dict of data (which is called
        "field meta") that identifies this field application
        (See `IntDataType` for an example).
        If this is not defined, this type can't be used as fields.
        `new_var_as_field` should be used together with this.
        """
        pass

    @abstractmethod
    def new_var_as_field(self, entity: "_EntityBase", **meta) -> "VarValue":
        """See `new_entity_field`.
        The `meta` are the same as field meta, and this should
        return the field specified by field meta for `entity`.
        """
        pass

class DefaultDataType(DataType):
    """A data type that carries no extra information like entity
    template.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @classmethod
    def name_no_generic(cls) -> str:
        return cls.name

    def __str__(self) -> str:
        return self.name

    def matches(self, other: "DataType") -> bool:
        return (isinstance(other, DefaultDataType)
                and issubclass(type(other), type(self)))
