"""Entity group -- a group of entities."""

__all__ = ["EGroupGeneric", "EGroupDataType", "EntityGroup"]

from typing import TYPE_CHECKING, List

from acaciamc.tools import axe, resultlib, method_of
from acaciamc.mccmdgen.mcselector import MCSelector
from acaciamc.mccmdgen.datatype import Storable
import acaciamc.mccmdgen.cmds as cmds
from .base import *
from .types import Type
from .entity_template import ETemplateDataType
from .entity_filter import EFilterDataType
from .entity import EntityDataType, EntityReference
from .boolean import AndGroup
from .integer import IntOpGroup
from .functions import BinaryFunction
from .generic import BinaryGeneric

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.datatype import DataType
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
        return EntityGroup(self.template, self.compiler)

    def get_var_initializer(self, var: "EntityGroup") -> AcaciaCallable:
        @axe.chop
        @axe.arg("all_entities", axe.LiteralBool(), default=False)
        def _new(compiler, all_entities: bool):
            """
            Create an empty entity group (unless all_entities is True).
            o: Engroup[E]  # A group of entities of template E
            o: Engroup[E] | (all_entities=True)  # Include all entities
            """
            # Remove all existsing entities on initialization
            if not all_entities:
                commands = var.clear()
            else:
                commands = ["tag @e add %s" % var.tag]
            return resultlib.commands(commands, compiler)
        return BinaryFunction(_new, self.compiler)

class EGroupGeneric(BinaryGeneric):
    @axe.chop_getitem
    @axe.arg("E", ETemplateDataType, rename="template")
    def getitem(self, template: "EntityTemplate"):
        return EGroupType(template, self.compiler)

class EGroupType(Type):
    def __init__(self, template: "EntityTemplate", compiler):
        self.template = template
        super().__init__(compiler)

    def datatype_hook(self):
        return EGroupDataType(self.template)

class EntityGroup(VarValue):
    def __init__(self, template: "EntityTemplate", compiler):
        super().__init__(EGroupDataType(template), compiler)
        self.template = template
        self.tag = self.compiler.allocate_entity_tag()
        SELF = self.get_selector().to_str()
        MEMBER_TYPE = EntityDataType(template)
        OPERAND_TYPE = EGroupDataType(template)

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
            res = EntityGroup(self.template, compiler)
            _, commands = (
                self.data_type.get_var_initializer(res).call([], {})
            )
            commands.append("tag %s add %s" % (SELF, res.tag))
            return res, commands
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
            res = AndGroup(operands=(), compiler=compiler)
            res.main.append(cmds.ExecuteCond("entity", SELF, invert=True))
            return res
        @method_of(self, "size")
        @axe.chop
        def _size(compiler: "Compiler"):
            res = IntOpGroup(init=None, compiler=compiler)
            res.write(
                lambda this, libs: cmds.ScbSetConst(this, 0),
                lambda this, libs: cmds.Execute(
                    [cmds.ExecuteEnv("as", SELF)],
                    runs=cmds.ScbAddConst(this, 1)
                )
            )
            return res
        @method_of(self, "to_single")
        @axe.chop
        def _to_single(compiler: "Compiler"):
            return EntityReference(self.get_selector(),
                                   self.template, compiler)
        @method_of(self, "includes")
        @axe.chop
        @axe.arg("ent", MEMBER_TYPE)
        def _includes(compiler: "Compiler", ent: "_EntityBase"):
            res = AndGroup(operands=(), compiler=compiler)
            selector = ent.get_selector()
            selector.tag(self.tag)
            res.main.append(cmds.ExecuteCond("entity", selector.to_str()))
            return res

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
