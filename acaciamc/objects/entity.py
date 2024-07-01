"""Entity of Acacia."""

__all__ = ['EntityDataType', 'TaggedEntity', 'EntityReference']

from typing import TYPE_CHECKING, List, Optional

from acaciamc.mccmdgen.datatype import Storable
from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.mcselector import MCSelector
from acaciamc.mccmdgen.utils import InvalidOpError

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.datatype import DataType
    from .entity_template import EntityTemplate


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

    def stringify(self) -> str:
        return self.to_str()

    def rawtextify(self, compiler):
        # To override default behavior of calling `stringify`.
        raise InvalidOpError

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
        """
        NOTE this default implementation assumes that clearing the
        target tag does not affect this object.
        """
        cmds = var.clear()
        cmds.append("tag %s add %s" % (self, var.tag))
        return cmds


class EntityReference(_EntityBase):
    def __init__(self, selector: MCSelector, template: "EntityTemplate",
                 cast_to: Optional["EntityTemplate"] = None):
        self.selector = selector
        super().__init__(template, cast_to)

    @classmethod
    def from_other(cls, other: _EntityBase):
        return cls(other.get_selector(), other.template)

    def _get_selector(self) -> MCSelector:
        return self.selector.copy()

    def cast_to(self, template):
        return EntityReference(self.selector, self.template, template)

    def export(self, var: "TaggedEntity", compiler):
        # Check if clearing the target tag would affect this object
        if var.tag in self.selector.get_tags():
            # By definition, an entity object must represent exactly one
            # entity, which means that this entity must satisfy the
            # selector, or else it's an undefined bahaviour.
            # XXX add runtime check to see if the entity actually
            # satisfies the selector.
            return []
        # Default implementation
        return super().export(var, compiler)


class TaggedEntity(_EntityBase, VarValue):
    def __init__(self, tag: str, template: "EntityTemplate",
                 cast_to: Optional["EntityTemplate"] = None):
        self.tag = tag
        super().__init__(template, cast_to)

    def cast_to(self, template):
        return TaggedEntity(self.tag, self.template, template)

    def export(self, var: "TaggedEntity", compiler):
        # Check self-assignment
        if var.tag == self.tag:
            return []
        return super().export(var, compiler)

    def swap(self, other: "TaggedEntity", compiler):
        # Check self-swapping
        if other.tag == self.tag:
            return []
        return super().swap(other, compiler)

    @classmethod
    def new_tag(cls, template: "EntityTemplate", compiler: "Compiler",
                cast_to: Optional["EntityTemplate"] = None):
        """Create a new entity tag that points to no entity."""
        return cls(
            compiler.allocate_entity_tag(),
            template, cast_to
        )

    def _get_selector(self) -> MCSelector:
        res = MCSelector("e")
        res.tag(self.tag)
        return res

    def clear(self) -> List[str]:
        # Clear the reference to entity that the tag is pointing to.
        return ["tag %s remove %s" % (self, self.tag)]
