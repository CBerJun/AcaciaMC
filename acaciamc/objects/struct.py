"""Collections of several variables at runtime."""

__all__ = ["StructDataType", "Struct"]

from itertools import chain
from typing import TYPE_CHECKING, Dict, Tuple

from acaciamc.error import *
from acaciamc.mccmdgen.datatype import SupportsEntityField, Storable
from acaciamc.mccmdgen.expr import *

if TYPE_CHECKING:
    from .entity import _EntityBase
    from .struct_template import StructTemplate
    from .types import DataType


class StructDataType(Storable, SupportsEntityField):
    def __init__(self, template: "StructTemplate"):
        super().__init__()
        self.template = template

    def __str__(self) -> str:
        return self.template.name

    @classmethod
    def name_no_generic(self) -> str:
        return "struct"

    def matches(self, other: "DataType") -> bool:
        return (isinstance(other, StructDataType) and
                other.template.is_subtemplate_of(self.template))

    def new_var(self, compiler) -> "Struct":
        return Struct.from_template(self.template, compiler)

    def new_entity_field(self, compiler):
        field_info: Dict[str, Tuple[dict, SupportsEntityField]] = {}
        for name, type_ in self.template.field_types.items():
            if not isinstance(type_, SupportsEntityField):
                raise Error(ErrorType.UNSUPPORTED_EFIELD_IN_STRUCT,
                            template=self.template.name, field_type=type_)
            submeta = type_.new_entity_field(compiler)
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
        return Struct(self.template, vars_)


class Struct(VarValue):
    def __init__(self, template: "StructTemplate", vars_: Dict[str, VarValue]):
        super().__init__(StructDataType(template))
        self.template = template
        self.vars = vars_
        self.attribute_table.update(vars_)

    @classmethod
    def from_template(cls, template: "StructTemplate", compiler):
        vars_ = {}
        for name, type_ in template.field_types.items():
            var = type_.new_var(compiler)
            vars_[name] = var
        return cls(template, vars_)

    def export(self, other_struct: "Struct", compiler) -> CMDLIST_T:
        return list(chain.from_iterable(
            self.vars[name].export(other_struct.vars[name], compiler)
            for name in other_struct.vars
            # `self` may have fields that `other_struct` doesn't have.
        ))

    def swap(self, other: "Struct", compiler) -> CMDLIST_T:
        return list(chain.from_iterable(
            swap_exprs(self.vars[name], other.vars[name], compiler)
            for name in self.vars
        ))
