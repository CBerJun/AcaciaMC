"""Values of "type" type in Acacia.
e.g. "int" is a "type".
"""

__all__ = ['TypeDataType', 'Type']

from typing import TYPE_CHECKING
from abc import ABCMeta, abstractmethod

from .base import *
from .none import NoneDataType
from acaciamc.error import *
from acaciamc.mccmdgen.datatype import DefaultDataType

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.datatype import DataType

class TypeDataType(DefaultDataType):
    name = "type"

class Type(ConstExpr, AcaciaCallable, metaclass=ABCMeta):
    """Base class for type of a variable that represents a type.
    (e.g. type of builtin "int" is `IntType`).
    """
    def __init__(self, compiler: "Compiler"):
        super().__init__(TypeDataType(compiler), compiler)
        self.func_repr = str(self.datatype_hook())
        self.do_init()

    def do_init(self):
        """Initialzer for `Type`s. This exists due to historical reason."""
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
            raise Error(ErrorType.CANT_CREATE_INSTANCE,
                        type_=str(self.datatype_hook()))
        if not isinstance(new, AcaciaCallable):
            raise TypeError("__new__ of Type objects must be a callable"
                            " expression")
        instance, cmds = new.call(args, keywords)
        # Call initializer of instance if exists
        initializer = instance.attribute_table.lookup('__init__')
        if initializer is not None:
            if not isinstance(initializer, AcaciaCallable):
                raise TypeError("__init__ of Type objects must be a callable"
                                " expression")
            ret, _cmds = initializer.call(args, keywords)
            if not ret.data_type.matches_cls(NoneDataType):
                raise TypeError("__init__ of Type objects return %r instead "
                                "of None" % str(ret.data_type))
            cmds.extend(_cmds)
        return instance, cmds

    @abstractmethod
    def datatype_hook(self) -> "DataType":
        pass
