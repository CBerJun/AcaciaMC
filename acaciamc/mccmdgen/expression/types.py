"""Values of "type" type in Acacia.
e.g. "int" is a "type".
"""

__all__ = ['TypeDataType', 'Type']

from typing import TYPE_CHECKING
from abc import ABCMeta, abstractmethod

try:  # Python 3.8+
    from typing import final
except ImportError:
    def final(func):
        return func

from .base import *
from .none import NoneDataType
from acaciamc.error import *
from acaciamc.mccmdgen.datatype import DefaultDataType

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.datatype import DataType

class TypeDataType(DefaultDataType):
    name = "type"

class Type(AcaciaExpr, metaclass=ABCMeta):
    """Base class for type of a variable that represents a type.
    (e.g. type of builtin "int" is `IntType`).
    """
    @final
    def __init__(self, compiler: "Compiler"):
        """Override `do_init` instead of this."""
        super().__init__(TypeDataType(), compiler)
        self.do_init()

    def do_init(self):
        """Initialzer for `Type`s -- override it instead of `__init__`.
        This exists due to history reason.
        """
        pass

    def call(self, args, keywords):
        """Calling a type is to create an instance of this type.
        Two things are done:
        1. call `self.__new__` and get `instance`
        2. call `instance.__init__` if exists.
        """
        # Call `__new__`
        new = self.attribute_table.lookup('__new__')
        if new is None:
            raise Error(ErrorType.CANT_CREATE_INSTANCE, type_=self.name)
        instance, cmds = new.call(args, keywords)
        # Call initializer of instance if exists
        initializer = instance.attribute_table.lookup('__init__')
        if initializer is not None:
            ret, _cmds = initializer.call(args, keywords)
            if not ret.data_type.matches_cls(NoneDataType):
                raise Error(ErrorType.INITIALIZER_RESULT, type_=self.name)
            cmds.extend(_cmds)
        return instance, cmds

    @abstractmethod
    def datatype_hook(self) -> "DataType":
        pass
