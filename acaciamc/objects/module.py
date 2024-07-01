"""Modules."""

__all__ = ['ModuleDataType', 'BinaryModule', 'AcaciaModule', 'BuiltModule']

import importlib.util
from typing import Dict, Optional

from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.symbol import SymbolTable


class ModuleDataType(DefaultDataType):
    name = 'module'


ctdt_module = CTDataType("module")


class BuiltModule:
    """Object that should be returned by acacia_build to specify a module."""

    def __init__(
            self,
            attributes: Optional[Dict[str, AcaciaExpr]] = None,
            init_cmds: Optional[CMDLIST_T] = None
    ):
        if attributes is None:
            attributes = {}
        if init_cmds is None:
            init_cmds = []
        self.attributes = attributes
        self.init_cmds = init_cmds


class BinaryModule(ConstExprCombined):
    """A binary module that is implemented in Python."""
    cdata_type = ctdt_module

    def __init__(self, path: str):
        """`path` is path to the binary module Python file."""
        super().__init__(ModuleDataType())
        self.path = path
        # get the module from `path`
        self.spec = importlib.util.spec_from_file_location(
            '<acacia module %r>' % path, path
        )
        self.py_module = importlib.util.module_from_spec(self.spec)

    def execute(self, compiler) -> CMDLIST_T:
        """
        Execute the code in the binary module Python file.
        Return the commands run by the module during initialization.
        """
        self.spec.loader.exec_module(self.py_module)
        # Call `acacia_build`
        # Binary modules should define a function named `acacia_build`,
        # which accepts 1 argument `compiler` and should return either
        # a `BuiltModule` or a `dict` containing the attributes of the
        # module (same as `BuiltModule.attributes`).
        res = self.py_module.acacia_build(compiler)
        if isinstance(res, dict):
            res = BuiltModule(res)
        for name, value in res.attributes.items():
            self.attribute_table.set(name, value)
        return res.init_cmds


class AcaciaModule(ConstExprCombined):
    """An Acacia module that is implemented in Acacia."""
    cdata_type = ctdt_module

    def __init__(self, table: SymbolTable):
        super().__init__(ModuleDataType())
        for name in table.all_names():
            if not (name in table.no_export or name.startswith('_')):
                self.attribute_table.set(name, table.get_raw(name))
