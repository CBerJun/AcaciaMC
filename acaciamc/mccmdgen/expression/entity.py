"""Entity of Acacia."""

__all__ = ['EntityDataType', 'TaggedEntity', 'EntityReference']

from typing import Tuple, TYPE_CHECKING, List, Optional

from acaciamc.constants import Config
from acaciamc.error import *
from acaciamc.mccmdgen.mcselector import MCSelector
from acaciamc.mccmdgen.datatype import Storable
import acaciamc.mccmdgen.cmds as cmds
from .base import *

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from .entity_template import EntityTemplate
    from .types import DataType

class EntityDataType(Storable):
    def __init__(self, template: "EntityTemplate"):
        self.template = template
        self.compiler = self.template.compiler

    def __str__(self) -> str:
        return "entity(%s)" % self.template.name

    @classmethod
    def name_no_generic(cls) -> str:
        return "entity"

    def matches(self, other: "DataType") -> bool:
        return (isinstance(other, EntityDataType) and
                other.template.is_subtemplate_of(self.template))

    def new_var(self, tmp=False) -> "TaggedEntity":
        var = TaggedEntity.from_empty(self.template, self.compiler)
        if tmp:
            self.compiler.add_tmp_entity(var)
        return var

class _EntityBase(AcaciaExpr):
    def __init__(self, template: "EntityTemplate", compiler,
                 cast_to: Optional["EntityTemplate"] = None):
        super().__init__(EntityDataType(template), compiler)
        self.cast_template = cast_to
        self.template = template
        self.template.register_entity(self)

    def __str__(self) -> str:
        return self.get_selector().to_str()

    def to_str(self) -> str:
        return str(self)

    def get_selector(self) -> MCSelector:
        # Caller owns the selector
        raise NotImplementedError

    def cast_to(self, template: "EntityTemplate"):
        raise NotImplementedError

    def export(self, var: "TaggedEntity"):
        cmds = var.clear()
        cmds.append("tag %s add %s" % (self, var.tag))
        return cmds

class EntityReference(_EntityBase):
    def __init__(self, selector: MCSelector, template: "EntityTemplate",
                 compiler, cast_to: Optional["EntityTemplate"] = None):
        self.selector = selector
        super().__init__(template, compiler, cast_to)

    def cmdstr(self) -> str:
        return str(self)

    def get_selector(self) -> MCSelector:
        return self.selector.copy()

    def cast_to(self, template):
        return EntityReference(
            self.selector, self.template, self.compiler, template
        )

class TaggedEntity(_EntityBase, VarValue):
    def __init__(self, template: "EntityTemplate", compiler: "Compiler",
                 cast_to: Optional["EntityTemplate"] = None):
        self.tag = compiler.allocate_entity_tag()
        super().__init__(template, compiler, cast_to)

    def cast_to(self, template):
        return TaggedEntity(self.template, self.compiler, template)

    @classmethod
    def from_template(cls, template: "EntityTemplate", compiler: "Compiler"
                      ) -> Tuple["TaggedEntity", CMDLIST_T]:
        """Create an entity from the template.
        Return a 2-tuple.
        Element 0: the `TaggedEntity`
        Element 1: initial commands to run
        """
        # Allocate an entity name to identify it
        name = compiler.allocate_entity_name()
        inst = cls(template, compiler)
        # Analyze template meta
        # NOTE meta only works when you create an entity using
        # `Template()` (Since this code is in `from_template` method).
        e_type = Config.entity_type
        e_pos = ([], Config.entity_pos)
        e_event = "*"
        for meta, value in template.metas.items():
            if meta == "type":
                # Entity type
                e_type = value
            elif meta == "position":
                # Position to summon the entity
                e_pos = value
            elif meta == "spawn_event":
                # Entity event to execute on spawn
                e_event = value
        if Config.mc_version >= (1, 19, 70):
            SUMMON = "summon {type} {pos} 0 0 {event} {name}"
        else:
            SUMMON = "summon {type} {pos} {event} {name}"
        return inst, [
            cmds.Execute(e_pos[0], cmds.Cmd(SUMMON.format(
                type=e_type, name=name, pos=e_pos[1], event=e_event
            ))),
            "tag @e[name=%s] add %s" % (name, inst.template.runtime_tag),
            "tag @e[name=%s] add %s" % (name, inst.tag)
        ]

    @classmethod
    def from_empty(cls, template: "EntityTemplate", compiler):
        # Create an entity reference (a tag), pointing to no entity.
        return cls(template, compiler)

    def get_selector(self) -> MCSelector:
        res = MCSelector("e")
        res.tag(self.tag)
        return res

    def cmdstr(self) -> str:
        return str(self)

    def clear(self) -> List[str]:
        # Clear the reference to entity that the tag is pointing to.
        return ["tag %s remove %s" % (self, self.tag)]
