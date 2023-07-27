"""Entity group -- a group of entities."""

__all__ = [
    "EGroupType", "EntityGroup",
    # Special value returned by Engroup.t(template)
    "GenericEGroup", "GenericEGroupType"
]

from typing import TYPE_CHECKING, List, Optional

from acaciamc.tools import axe, method_of
from acaciamc.mccmdgen.mcselector import MCSelector
from .base import *
from .types import DataType, Type
from .entity_template import ETemplateType
from .entity_filter import EFilterType
from .entity import EntityReference
from .boolean import AndGroup
from .integer import IntOpGroup

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from .entity_template import EntityTemplate
    from .entity_filter import EntityFilter
    from .entity import _EntityBase

class GenericEGroupType(Type):
    name = "Engroup.t"

class GenericEGroup(AcaciaExpr):
    """Thing that is returned by Engroup.t()."""
    def __init__(self, data_type: DataType, compiler: "Compiler"):
        super().__init__(
            DataType.from_type_cls(GenericEGroupType, compiler), compiler
        )
        self.dt = data_type

class EGroupType(Type):
    name = "Engroup"

    def do_init(self):
        @method_of(self, "__new__")
        @axe.chop
        @axe.arg("template", ETemplateType, default=None)
        def _new(compiler: "Compiler", template: Optional["EntityTemplate"]):
            if template is None:
                template = compiler.base_template
            return EntityGroup(template, compiler)
        @method_of(self, "all_entities")
        @axe.chop
        def _all_entities(compiler: "Compiler"):
            res = EntityGroup(compiler.base_template, compiler)
            cmds = ["tag @e add %s" % res.tag]
            return res, cmds
        @method_of(self, "t")
        @axe.chop
        @axe.arg("template", ETemplateType)
        def _t(compiler: "Compiler", template: "EntityTemplate"):
            return GenericEGroup(
                DataType.from_entity_group(template, compiler), compiler
            )
    def new_var(self, template: "EntityTemplate", tmp=False):
        var = EntityGroup(template, self.compiler)
        if tmp:
            self.compiler.add_tmp_entity(var)
        return var

class EntityGroup(VarValue):
    def __init__(self, template: "EntityTemplate", compiler):
        super().__init__(
            DataType.from_entity_group(template, compiler), compiler
        )
        self.template = template
        self.tag = self.compiler.allocate_entity_tag()
        SELF = "@e[tag=%s]" % self.tag
        MEMBER_TYPE = DataType.from_entity(template, compiler)
        OPERAND_TYPE = DataType.from_entity_group(template, compiler)

        @method_of(self, "select")
        @axe.chop
        @axe.arg("filter", EFilterType, rename="filter_")
        def _select(compiler, filter_: "EntityFilter"):
            cmds = filter_.dump("tag {selected} add %s" % self.tag)
            return self, cmds
        @method_of(self, "drop")
        @axe.chop
        @axe.arg("filter", EFilterType, rename="filter_")
        def _drop(compiler, filter_: "EntityFilter"):
            cmds = filter_.dump("tag {selected} remove %s" % self.tag)
            return self, cmds
        @method_of(self, "filter")
        @axe.chop
        @axe.arg("filter", EFilterType, rename="filter_")
        def _filter(compiler: "Compiler", filter_: "EntityFilter"):
            tmp = compiler.allocate_entity_tag()
            cmds = filter_.dump("tag {selected} add %s" % tmp)
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
            cmds = ["tag %s add %s" % (SELF, res.tag)]
            return res, cmds
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
            res.main.append("unless entity %s" % SELF)
            return res
        @method_of(self, "size")
        @axe.chop
        def _size(compiler: "Compiler"):
            res = IntOpGroup(init=None, compiler=compiler)
            res.write("scoreboard players set {this} 0",
                      ("execute as %s run "
                       "scoreboard players add {this} 1") % SELF)
            return res
        @method_of(self, "to_single")
        @axe.chop
        def _to_single(compiler: "Compiler"):
            self_selector = MCSelector("e")
            self_selector.tag(self.tag)
            return EntityReference(self_selector, self.template, compiler)
        @method_of(self, "includes")
        @axe.chop
        @axe.arg("ent", DataType.from_entity(self.template, compiler))
        def _includes(compiler: "Compiler", ent: "_EntityBase"):
            res = AndGroup(operands=(), compiler=compiler)
            selector = ent.get_selector()
            selector.tag(self.tag)
            res.main.append("if entity %s" % selector.to_str())
            return res

    def export(self, var: "EntityGroup") -> List[str]:
        cmds = var.clear()
        cmds.append("tag @e[tag=%s] add %s" % (self.tag, var.tag))
        return cmds

    def clear(self) -> List[str]:
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
