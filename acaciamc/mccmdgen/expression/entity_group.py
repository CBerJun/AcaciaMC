"""Entity group -- a group of entities."""

__all__ = ["EGroupDataType", "EGroupGeneric", "EGroupType", "EntityGroup"]

from typing import TYPE_CHECKING, List

from acaciamc.tools import axe, resultlib, method_of, cmethod_of
from acaciamc.mccmdgen.mcselector import MCSelector
from acaciamc.mccmdgen.datatype import Storable
import acaciamc.mccmdgen.cmds as cmds
from .base import *
from .entity_template import ETemplateDataType
from .entity_filter import EFilterDataType
from .entity import EntityDataType, EntityReference
from .boolean import WildBool
from .integer import IntOpGroup, IntOp
from .functions import BinaryFunction, ConstructorFunction
from .generic import BinaryGeneric
from .types import TypeDataType

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.datatype import DataType
    from .integer import IntVar
    from .entity_template import EntityTemplate
    from .entity_filter import EntityFilter
    from .entity import _EntityBase

class EGroupDataType(Storable):
    name = "Engroup"

    def __init__(self, template: "EntityTemplate"):
        super().__init__(template.compiler)
        self.template = template

    def __str__(self) -> str:
        return "Engroup[%s]" % self.template.name

    @classmethod
    def name_no_generic(cls) -> str:
        return "Engroup"

    def matches(self, other: "DataType") -> bool:
        return (isinstance(other, EGroupDataType) and
                other.template.is_subtemplate_of(self.template))

    def new_var(self):
        return EntityGroup.from_template(self.template, self.compiler)

class EGroupGeneric(BinaryGeneric):
    def __init__(self, compiler):
        super().__init__(compiler)
        @cmethod_of(self, "__getitem__")
        @axe.chop
        @axe.arg("E", ETemplateDataType, rename="template")
        def _getitem(compiler, template: "EntityTemplate"):
            return EGroupType(template, compiler)

class EGroupType(ConstExpr, ConstructorFunction):
    def __init__(self, template: "EntityTemplate", compiler):
        super().__init__(TypeDataType(compiler), compiler)
        self.template = template

    def initialize(
            self, instance: "EntityGroup",
            args: "ARGS_T", keywords: "KEYWORDS_T",
        ) -> CMDLIST_T:
        @axe.chop
        def _call_me(compiler: "Compiler"):
            return resultlib.commands(instance.clear(), compiler)
        _, c = BinaryFunction(_call_me, self.compiler).call(args, keywords)
        return c

    def datatype_hook(self):
        return EGroupDataType(self.template)

class IntEntityCount(IntOp):
    init = True

    def __init__(self, entity: str) -> None:
        self.entity = entity

    def resolve(self, var: "IntVar") -> CMDLIST_T:
        return [
            cmds.ScbSetConst(var.slot, 0),
            cmds.Execute(
                [cmds.ExecuteEnv("as", self.entity)],
                runs=cmds.ScbAddConst(var.slot, 1)
            )
        ]

class EntityGroup(VarValue):
    def __init__(self, data_type: EGroupDataType, compiler):
        super().__init__(data_type, compiler)
        self.template = data_type.template
        self.tag = self.compiler.allocate_entity_tag()
        SELF = self.get_selector().to_str()
        MEMBER_TYPE = EntityDataType(self.template)
        OPERAND_TYPE = EGroupDataType(self.template)

        @method_of(self, "select")
        @axe.chop
        @axe.arg("filter", EFilterDataType, rename="filter_")
        def _select(compiler, filter_: "EntityFilter"):
            """
            .select(filter: Enfilter) -> EntityGroup
            Selects entities from all entities in the world that match
            the filter and add them to this entity group.
            """
            cmds = filter_.dump("tag {selected} add %s" % self.tag)
            return self, cmds
        @method_of(self, "drop")
        @axe.chop
        @axe.arg("filter", EFilterDataType, rename="filter_")
        def _drop(compiler, filter_: "EntityFilter"):
            """
            .drop(filter: Enfilter) -> EntityGroup
            Selects entities from this entity group that match the
            filter and remove them.
            """
            cmds = filter_.dump(
                "tag {selected} remove %s" % self.tag,
                among_tag=self.tag
            )
            return self, cmds
        @method_of(self, "filter")
        @axe.chop
        @axe.arg("filter", EFilterDataType, rename="filter_")
        def _filter(compiler: "Compiler", filter_: "EntityFilter"):
            """
            .filter(filter: Enfilter) -> EntityGroup
            Selects entities from this entity group that match the
            filter and only keep them.
            """
            tmp = compiler.allocate_entity_tag()
            cmds = filter_.dump(
                "tag {selected} add %s" % tmp,
                among_tag=self.tag
            )
            cmds.append("tag @e[tag={0},tag=!{1}] remove {0}".format(
                self.tag, tmp
            ))
            cmds.append("tag @e[tag={0}] remove {0}".format(tmp))
            return self, cmds
        @method_of(self, "extend")
        @axe.chop
        @axe.arg("other", OPERAND_TYPE)
        def _extend(compiler, other: "EntityGroup"):
            return self, ["tag @e[tag=%s] add %s" % (other.tag, self.tag)]
        @method_of(self, "subtract")
        @axe.chop
        @axe.arg("other", OPERAND_TYPE)
        def _subtract(compiler, other: "EntityGroup"):
            return self, ["tag @e[tag=%s] remove %s" % (other.tag, self.tag)]
        @method_of(self, "intersect")
        @axe.chop
        @axe.arg("other", OPERAND_TYPE)
        def _intersect(compiler, other: "EntityGroup"):
            return self, ["tag @e[tag=!%s] remove %s" % (other.tag, self.tag)]
        @method_of(self, "copy")
        @axe.chop
        def _copy(compiler):
            res = self.data_type.new_var()
            return res, self.export(res)
        @method_of(self, "clear")
        @axe.chop
        def _clear(compiler):
            return self, ["tag %s remove %s" % (SELF, self.tag)]
        @method_of(self, "add")
        @axe.chop
        @axe.star_arg("entities", MEMBER_TYPE)
        def _add(compiler, entities: List["_EntityBase"]):
            return self, ["tag %s add %s" % (entity, self.tag)
                          for entity in entities]
        @method_of(self, "remove")
        @axe.chop
        @axe.star_arg("entities", MEMBER_TYPE)
        def _remove(compiler, entities: List["_EntityBase"]):
            return self, ["tag %s remove %s" % (entity, self.tag)
                          for entity in entities]
        @method_of(self, "is_empty")
        @axe.chop
        def _is_empty(compiler: "Compiler"):
            subcmds = [cmds.ExecuteCond("entity", SELF, invert=True)]
            return WildBool(subcmds, [], compiler)
        @method_of(self, "size")
        @axe.chop
        def _size(compiler: "Compiler"):
            return IntOpGroup(init=IntEntityCount(SELF), compiler=compiler)
        @method_of(self, "to_single")
        @axe.chop
        def _to_single(compiler: "Compiler"):
            return EntityReference(self.get_selector(),
                                   self.template, compiler)
        @method_of(self, "has")
        @axe.chop
        @axe.arg("ent", MEMBER_TYPE)
        @axe.slash
        def _has(compiler: "Compiler", ent: "_EntityBase"):
            selector = ent.get_selector()
            selector.tag(self.tag)
            subcmds = [cmds.ExecuteCond("entity", selector.to_str())]
            return WildBool(subcmds, [], compiler)

    @classmethod
    def from_template(cls, template: "EntityTemplate", compiler: "Compiler"):
        return cls(EGroupDataType(template), compiler)

    def export(self, var: "EntityGroup") -> CMDLIST_T:
        cmds = var.clear()
        cmds.append("tag @e[tag=%s] add %s" % (self.tag, var.tag))
        return cmds

    def get_selector(self) -> "MCSelector":
        res = MCSelector("e")
        res.tag(self.tag)
        return res

    def clear(self) -> CMDLIST_T:
        return ["tag @e[tag={0}] remove {0}".format(self.tag)]

    def iadd(self, other):
        if isinstance(other, EntityGroup):
            expr, cmds = self.attribute_table.lookup("extend").call(
                [other], {}
            )
            assert expr is self
            return cmds
        raise TypeError

    def isub(self, other):
        if isinstance(other, EntityGroup):
            expr, cmds = self.attribute_table.lookup("subtract").call(
                [other], {}
            )
            assert expr is self
            return cmds
        raise TypeError
