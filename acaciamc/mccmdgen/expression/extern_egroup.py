"""
`ExternEngroup` objects.

When dealing with entities that exist already in the world, how can
Acacia know which template to use? Well, `ExternEngroup` can be
used to handle those entities. Also, by using this you may tell
Acacia explicitly which template to use for an entity.
    import world
    entity MyTemp:
        pass
    entity Diamond:
        pass
    ex: ExternEngroup[MyTemp]
    ex2: ExternEngroup[Diamond]
    ex.select(Enfilter().is_type("armor_stand").is_name("foo"))
    for e in ex:
        # `e` here is not `MyTemp`, though it might later be marked
        # as such.
        if world.is_block(Pos(e).offset(y=-1), "diamond_block"):
            ex2.add(e)
            ex.remove(e)
In the example we select all armor stands with name "foo" and add
them to `ex2` if they are on diamond block, or else to `ex`. `ex`
is a potential group of `MyTemp` and `ex2` is a potential group of
`Diamond`.
    # Mark all current entities in `ex` as `MyTemp`, and return the
    # normal `Engroup`.
    my_group := ex.resolve()
    diamond_group := ex2.resolve()
Now `my_group` is of type `Engroup[MyTemp]` and `diamond_group` is
of type `Engroup[Diamond]`.
You should make sure no entity is registered in 2 different
templates, or the behavior is undefined. Registering the same entity
on exact same template is allowed. This should be used to handle all
external entities safely.
"""

__all__ = [
    "ExternEGroupDataType", "ExternEGroupType", "ExternEGroupGeneric",
    "ExternEGroup"
]

from typing import TYPE_CHECKING

from acaciamc.tools import axe, resultlib, cmethod_of
from .base import *
from .entity_group import *
from .entity_template import ETemplateDataType
from .functions import (
    ConstructorFunction, FunctionDataType, BinaryFunction, ctdt_function
)

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from .entity_template import EntityTemplate

class ExternEGroupDataType(EGroupDataType):
    def __init__(self, template: "EntityTemplate"):
        super().__init__(template.compiler.external_template)
        self.__template = template

    def __str__(self) -> str:
        return "ExternEngroup[%s]" % self.__template.name

    @classmethod
    def name_no_generic(cls) -> str:
        return "ExternEngroup"

    def new_var(self):
        return ExternEGroup(self.__template, self.compiler)

class ExternEGroupType(EGroupType):
    def datatype_hook(self):
        return ExternEGroupDataType(self.template)

class ExternEGroupGeneric(EGroupGeneric):
    def __init__(self, compiler):
        super().__init__(compiler)
        @cmethod_of(self, "__getitem__")
        @axe.chop
        @axe.arg("template", ETemplateDataType)
        def _getitem(compiler, template: "EntityTemplate"):
            return ExternEGroupType(template, compiler)

class _ExternEGroupResolve(ConstExprCombined, ConstructorFunction):
    cdata_type = ctdt_function

    def __init__(self, owner: "ExternEGroup", compiler: "Compiler"):
        super().__init__(FunctionDataType(compiler), compiler)
        self.owner = owner
        self.func_repr = "<resolve of %s>" % str(self.owner.data_type)

    def initialize(
            self, instance: "EntityGroup",
            args: "ARGS_T", keywords: "KEYWORDS_T"
        ) -> "CALLRET_T":
        template = self.owner.extern_template
        SELF = self.owner.get_selector().to_str()
        RESOLVE_CTOR = EGroupType(template, self.compiler)
        @axe.chop
        def _call_me(compiler: "Compiler"):
            commands = RESOLVE_CTOR.initialize(instance, [], {})
            commands.append("tag %s add %s" % (SELF, template.runtime_tag))
            commands.append("tag %s add %s" % (SELF, instance.tag))
            return resultlib.commands(commands, compiler)
        _, c = BinaryFunction(_call_me, self.compiler).call(args, keywords)
        return c

    def _var_type(self):
        return EGroupDataType(self.owner.extern_template)

class ExternEGroup(EntityGroup):
    def __init__(self, template: "EntityTemplate", compiler: "Compiler"):
        super().__init__(ExternEGroupDataType(template), compiler)
        self.attribute_table.set(
            "resolve", _ExternEGroupResolve(self, compiler)
        )
        self.extern_template = template
