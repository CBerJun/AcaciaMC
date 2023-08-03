"""Collections of several variables at runtime."""

__all__ = ["StructType", "Struct"]

from typing import TYPE_CHECKING, List, Dict, Tuple

from .base import *
from .types import DataType, Type
from acaciamc.error import *

if TYPE_CHECKING:
    from .entity import _EntityBase
    from .struct_template import StructTemplate

class StructType(Type):
    name = "struct"

    def new_var(self, template: "StructTemplate", tmp=False) -> "Struct":
        return Struct.from_template(template, self.compiler, tmp=tmp)

    def new_entity_field(self, template: "StructTemplate"):
        field_info: Dict[str, Tuple[dict, DataType]] = {}
        for name, type_ in template.field_types.items():
            try:
                submeta = type_.new_entity_field()
            except NotImplementedError:
                raise Error(ErrorType.UNSUPPORTED_EFIELD_IN_STRUCT,
                            template=template.name, field_type=type_)
            else:
                field_info[name] = (submeta, type_)
        return {"template": template, "field_info": field_info}

    def new_var_as_field(self, entity: "_EntityBase",
                         template: "StructTemplate",
                         field_info: Dict[str, Tuple[dict, DataType]]
                        ) -> "Struct":
        vars_ = {}
        for name, (submeta, type_) in field_info.items():
            subvar = type_.new_var_as_field(entity, **submeta)
            vars_[name] = subvar
        return Struct(template, vars_, self.compiler)

class Struct(VarValue):
    def __init__(self, template: "StructTemplate",
                 vars_: Dict[str, VarValue], compiler):
        super().__init__(DataType.from_struct(template, compiler), compiler)
        self.template = template
        self.vars = vars_
        self.attribute_table.update(vars_)

    @classmethod
    def from_template(cls, template: "StructTemplate", compiler, **kwds):
        vars_ = {}
        for name, type_ in template.field_types.items():
            try:
                var = type_.new_var(**kwds)
            except NotImplementedError:
                raise Error(ErrorType.UNSUPPORTED_SFIELD_TYPE,
                            field_type=type_)
            else:
                vars_[name] = var
        return cls(template, vars_, compiler)

    def export(self, other_struct: "Struct") -> List[str]:
        res = []
        for name in other_struct.vars:
            res.extend(self.vars[name].export(other_struct.vars[name]))
        return res
