"""Entity of Acacia."""

__all__ = ['EntityDataType', 'TaggedEntity', 'EntityReference']

from typing import Tuple, TYPE_CHECKING, List, Optional

from acaciamc.error import *
from acaciamc.mccmdgen.mcselector import MCSelector
from acaciamc.mccmdgen.datatype import Storable
from acaciamc.mccmdgen.expr import *
import acaciamc.mccmdgen.cmds as cmds
from .spawn_info import SpawnInfo

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.datatype import DataType
    from .entity_template import EntityTemplate

SUMMON_Y = -75  # must be below -64 so it's not reachable
SUMMON = "summon {type} ~ {y} ~{rot} {event}{name}"

class EntityDataType(Storable):
    def __init__(self, template: "EntityTemplate"):
        super().__init__()
        self.template = template

    def __str__(self) -> str:
        return self.template.name

    @classmethod
    def name_no_generic(cls) -> str:
        return "entity"

    def matches(self, other: "DataType") -> bool:
        return (isinstance(other, EntityDataType) and
                other.template.is_subtemplate_of(self.template))

    def new_var(self, compiler) -> "TaggedEntity":
        return TaggedEntity.new_tag(self.template, compiler)

class _EntityBase(AcaciaExpr):
    def __init__(self, template: "EntityTemplate",
                 cast_to: Optional["EntityTemplate"] = None):
        super().__init__(EntityDataType(template))
        self.cast_template = cast_to
        self.template = template
        self.template.register_entity(self)

    def __str__(self) -> str:
        return self.to_str()

    def to_str(self) -> str:
        return self.get_selector().to_str()

    def cmdstr(self) -> str:
        return self.to_str()

    def get_selector(self) -> MCSelector:
        res = self._get_selector()
        if res.var == "e" or res.var == "a":
            res.limit(1)
        return res

    def _get_selector(self) -> MCSelector:
        # Caller owns the selector
        raise NotImplementedError

    def cast_to(self, template: "EntityTemplate"):
        raise NotImplementedError

    def export(self, var: "TaggedEntity", compiler):
        cmds = var.clear()
        cmds.append("tag %s add %s" % (self, var.tag))
        return cmds

class EntityReference(_EntityBase):
    def __init__(self, selector: MCSelector, template: "EntityTemplate",
                 cast_to: Optional["EntityTemplate"] = None):
        self.selector = selector
        super().__init__(template, cast_to)

    def _get_selector(self) -> MCSelector:
        return self.selector.copy()

    def cast_to(self, template):
        return EntityReference(self.selector, self.template, template)

class TaggedEntity(_EntityBase, VarValue):
    def __init__(self, tag: str, template: "EntityTemplate",
                 cast_to: Optional["EntityTemplate"] = None):
        self.tag = tag
        super().__init__(template, cast_to)

    def cast_to(self, template):
        return TaggedEntity(self.tag, self.template, template)

    @classmethod
    def new_tag(cls, template: "EntityTemplate", compiler: "Compiler",
                cast_to: Optional["EntityTemplate"] = None):
        """Create a new entity tag that points to no entity."""
        return cls(
            compiler.allocate_entity_tag(),
            template, cast_to
        )

    @classmethod
    def summon_new(
        cls, template: "EntityTemplate", compiler: "Compiler",
        _instance: Optional["TaggedEntity"] = None,
        info: Optional["SpawnInfo"] = None,
    ) -> Tuple["TaggedEntity", CMDLIST_T]:
        """Summon an entity of given template.
        Return a 2-tuple.
        Element 0: the `TaggedEntity`
        Element 1: initial commands to run
        """
        e_type = compiler.cfg.entity_type
        e_pos = ([], compiler.cfg.entity_pos)
        e_event = "*"
        e_name = ""
        e_rot = " 0 0" if compiler.cfg.mc_version >= (1, 19, 70) else ""
        if info is not None:
            f = info.fields
            if f.type is not None:
                e_type = f.type
            if f.pos is not None:
                e_pos = (f.pos.context, "~ ~ ~")
            if f.event is not None:
                e_event = f.event
            if f.name is not None:
                e_name = f" {cmds.mc_str(f.name)}"
        if _instance is None:
            inst = cls.new_tag(template, compiler)
        else:
            inst = _instance
        return inst, [
            cmds.Execute(
                [cmds.ExecuteEnv("at", "@p")],
                SUMMON.format(
                    type=e_type, name=e_name, rot=e_rot,
                    y=SUMMON_Y, event=e_event
                )
            ),
            *inst.clear(),
            cmds.Execute(
                [cmds.ExecuteEnv("at", "@p")],
                "tag @e[x=~,y=%d,z=~,dx=0,dy=0,dz=0] add %s" % (
                    SUMMON_Y, inst.tag
                )
            ),
            cmds.Execute(e_pos[0], "tp %s %s" % (inst.to_str(), e_pos[1])),
            "tag %s add %s" % (inst.to_str(), template.runtime_tag)
        ]

    def _get_selector(self) -> MCSelector:
        res = MCSelector("e")
        res.tag(self.tag)
        return res

    def clear(self) -> List[str]:
        # Clear the reference to entity that the tag is pointing to.
        return ["tag %s remove %s" % (self, self.tag)]
