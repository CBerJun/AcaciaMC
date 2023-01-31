# Modules in Acacia
from .base import *
from .types import BuiltinModuleType
from ..symbol import *
from ...error import *

import importlib.util

__all__ = ['BinaryModule', 'AcaciaModule']

class BinaryModule(AcaciaExpr):
    # A BinaryModule that is implemented in Python
    def __init__(self, path: str, compiler):
        # path: .py file path
        super().__init__(compiler.types[BuiltinModuleType], compiler)
        self.path = path
        # get the module from `path`
        try:
            spec = importlib.util.spec_from_file_location('<acaciamod>', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as err:
            compiler.error(ErrorType.IO, message = str(err))
        # Call `acacia_build`
        # binary modules should define a callable object named `acacia_build`,
        # which accepts 1 argument `compiler` and should return a dict:
        # keys are str (showing the attributes to export) and
        # values are AcaciaExpr (showing the values of attributes)
        if not hasattr(module, 'acacia_build'):
            self._module_error('can\'t find acacia_build')
        if not hasattr(module.acacia_build, '__call__'):
            self._module_error('acacia_build should be callable')
        exports = module.acacia_build(self.compiler)
        if not isinstance(exports, dict):
            self._module_error('acacia_build should return dict')
        for name, value in exports.items():
            if not isinstance(name, str):
                self._module_error('acacia_build return key should be str')
            if not isinstance(value, AcaciaExpr):
                self._module_error('acacia_build value should be AcaciaExpr')
            self.attribute_table.create(name, value)
    
    def _module_error(self, message: str):
        raise ValueError(repr(self.path) + ': ' + message)

class AcaciaModule(AcaciaExpr):
    # An AcaciaModule that is implemented in Acacia
    def __init__(self, table: SymbolTable, compiler):
        # table: the attributes from the module
        super().__init__(compiler.types[BuiltinModuleType], compiler)
        self.attribute_table = AttributeTable.from_other(table)
