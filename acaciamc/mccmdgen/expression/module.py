"""Modules."""

__all__ = ['ModuleDataType', 'BinaryModule', 'AcaciaModule']

import importlib.util

from .base import *
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.symbol import SymbolTable
from acaciamc.ctexec.expr import CTDataType
from acaciamc.error import *

class ModuleDataType(DefaultDataType):
    name = 'module'

ctdt_module = CTDataType("module")

class BinaryModule(ConstExprCombined):
    """A binary module that is implemented in Python."""
    cdata_type = ctdt_module

    def __init__(self, path: str, compiler):
        """`path` is .py file path."""
        super().__init__(ModuleDataType(compiler), compiler)
        self.path = path
        # get the module from `path`
        spec = importlib.util.spec_from_file_location(
            '<acacia module %r>' % path, path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
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
            self.attribute_table.set(name, value)

    def _module_error(self, message: str):
        raise ValueError(repr(self.path) + ': ' + message)

class AcaciaModule(ConstExprCombined):
    """An Acacia module that is implemented in Acacia."""
    cdata_type = ctdt_module

    def __init__(self, table: SymbolTable, compiler):
        super().__init__(ModuleDataType(compiler), compiler)
        for name in table.all_names():
            if not (name in table.no_export or name.startswith('_')):
                self.attribute_table.set(name, table.get_raw(name))
