"""Collections of several variables at runtime."""

__all__ = ["StructDataType", "Struct"]

from typing import TYPE_CHECKING, Dict, Tuple

from .base import *
from acaciamc.mccmdgen.datatype import SupportsEntityField, Storable
from acaciamc.error import *

if TYPE_CHECKING:
    from .entity import _EntityBase
    from .struct_template import StructTemplate
    from .types import DataType

class StructDataType(Storable, SupportsEntityField):
    def __init__(self, template: "StructTemplate"):
        self.template = template
        super().__init__(template.compiler)

    def __str__(self) -> str:
        return "struct(%s)" % self.template.name

    @classmethod
    def name_no_generic(self) -> str:
        return "struct"

    def matches(self, other: "DataType") -> bool:
        return (isinstance(other, StructDataType) and
                other.template.is_subtemplate_of(self.template))

    def new_var(self) -> "Struct":
        return Struct.from_template(self.template, self.compiler)

    def new_entity_field(self):
        field_info: Dict[str, Tuple[dict, SupportsEntityField]] = {}
        for name, type_ in self.template.field_types.items():
            if not isinstance(type_, SupportsEntityField):
                raise Error(ErrorType.UNSUPPORTED_EFIELD_IN_STRUCT,
                            template=self.template.name, field_type=type_)
            submeta = type_.new_entity_field()
            field_info[name] = (submeta, type_)
        return {"field_info": field_info}

    def new_var_as_field(
            self, entity: "_EntityBase",
            field_info: Dict[str, Tuple[dict, SupportsEntityField]]
        ) -> "Struct":
        vars_ = {}
        for name, (submeta, type_) in field_info.items():
            subvar = type_.new_var_as_field(entity, **submeta)
            vars_[name] = subvar
        return Struct(self.template, vars_, self.compiler)

class Struct(VarValue):
    def __init__(self, template: "StructTemplate",
                 vars_: Dict[str, VarValue], compiler):
        super().__init__(StructDataType(template), compiler)
        self.template = template
        self.vars = vars_
        self.attribute_table.update(vars_)

    @classmethod
    def from_template(cls, template: "StructTemplate", compiler):
        vars_ = {}
        for name, type_ in template.field_types.items():
            var = type_.new_var()
            vars_[name] = var
        return cls(template, vars_, compiler)

    def export(self, other_struct: "Struct") -> CMDLIST_T:
        res = []
        for name in other_struct.vars:
            res.extend(self.vars[name].export(other_struct.vars[name]))
        return res

    def swap(self, other: "Struct") -> CMDLIST_T:
        res = []
        for name in other.vars:
            res.extend(self.compiler.swap_exprs(
                self.vars[name], other.vars[name]
            ))
        return res
