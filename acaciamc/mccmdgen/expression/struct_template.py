"""Struct template."""

__all__ = ["StructTemplateDataType", "StructTemplate"]

from typing import List, Dict, TYPE_CHECKING

from .base import *
from .struct import StructDataType
from acaciamc.error import *
from acaciamc.mccmdgen.datatype import DefaultDataType

if TYPE_CHECKING:
    from acaciamc.mccmdgen.datatype import Storable

class StructTemplateDataType(DefaultDataType):
    name = "struct_template"

class StructTemplate(AcaciaExpr):
    def __init__(self, name: str, field: Dict[str, "Storable"],
                 bases: List["StructTemplate"], compiler):
        super().__init__(StructTemplateDataType(), compiler)
        self.name = name
        self.bases = bases
        self.field_types = field
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
