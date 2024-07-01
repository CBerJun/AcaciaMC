"""Struct template."""

__all__ = ["StructTemplateDataType", "StructTemplate"]

from typing import List, Dict, Optional, TYPE_CHECKING

from acaciamc.error import *
from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.utils import apply_decorators
from acaciamc.tools import axe, resultlib
from .functions import ConstructorFunction, BinaryFunction
from .struct import StructDataType, Struct

if TYPE_CHECKING:
    from acaciamc.mccmdgen.datatype import Storable


class StructTemplateDataType(DefaultDataType):
    name = "struct_template"


ctdt_structtemplate = CTDataType("struct_template")


class StructTemplate(ConstExprCombined, ConstructorFunction):
    cdata_type = ctdt_structtemplate

    def __init__(self, name: str, field: Dict[str, "Storable"],
                 bases: List["StructTemplate"], source=None):
        super().__init__(StructTemplateDataType())
        self.name = name
        self.bases = bases
        self.field_types = field
        self.func_repr = name
        self.source = source
        # Merge attributes from ancestors.
        for base in bases:
            for name, type_ in base.field_types.items():
                if name in self.field_types:
                    raise Error(ErrorType.SFIELD_MULTIPLE_DEFS, attr=name)
                self.field_types[name] = type_

    def datatype_hook(self):
        return StructDataType(template=self)

    def is_subtemplate_of(self, template: "StructTemplate") -> bool:
        """Return whether `template` is sub-template of this.
        This itself is treated as its own sub-template.
        """
        if template is self:
            return True
        if template in self.bases:
            return True
        return any(base.is_subtemplate_of(template) for base in self.bases)

    def initialize(
            self, instance: "Struct", compiler,
            args: "ARGS_T", keywords: "KEYWORDS_T"
    ):
        @axe.chop
        @axe.star
        @apply_decorators([
            axe.arg(name, type_, default=None)
            for name, type_ in self.field_types.items()
        ])
        def _call_me(compiler, **fields: Optional[AcaciaExpr]):
            commands = []
            for name, value in fields.items():
                if value is None:
                    continue
                commands.extend(value.export(instance.vars[name], compiler))
            return resultlib.commands(commands)

        _, c = BinaryFunction(_call_me).call(args, keywords, compiler)
        return c
