"""
`ExternEngroup` objects.

When dealing with entities that exist already in the world, how can
Acacia know which template to use? Well, `ExternEngroup` allows you to
tell Acacia explicitly which template to use for those entities.
    import world
    entity MyTemp:
        pass
    entity Diamond:
        pass
    ex := ExternEngroup()
    ex2 := ExternEngroup()
    ex.select(Enfilter().is_type("armor_stand").is_name("foo"))
    for e in ex:
        # Here `e` is an entity with a special template that is not even
        # a subtemplate of `Entity`.
        if world.is_block(Pos(e).offset(y=-1), "diamond_block"):
            ex2.add(e)
            ex.remove(e)
In the example we select all armor stands with name "foo" and add
them to `ex2` if they are on diamond block, or else to `ex`.
    # Mark all current entities in `ex` as `MyTemp`, and get the
    # resolved `Engroup[MyTemp]`.
    my_group := ex.resolve(MyTemp)
    diamond_group := ex2.resolve(Diamond)
Now `my_group` is of type `Engroup[MyTemp]` and `diamond_group` is
of type `Engroup[Diamond]`.
Selecting entities that already have a template using an
`ExternEngroup` is allowed, but just make sure no entity is registered
in 2 different templates. Registering the same entity on exact same
template is allowed, though.
"""

__all__ = ["ExternEGroupDataType", "ExternEGroupType", "ExternEGroup"]

from typing import TYPE_CHECKING

from acaciamc.localization import localize
from acaciamc.mccmdgen import cmds
from acaciamc.mccmdgen.expr import *
from acaciamc.tools import axe
from .entity_group import *
from .entity_template import ETemplateDataType
from .functions import (
    ConstructorFunction, FunctionDataType, BinaryFunction, ctdt_function
)

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from .entity_template import EntityTemplate


class ExternEGroupDataType(EGroupDataType):
    def __init__(self, compiler: "Compiler"):
        super().__init__(compiler.external_template)

    def __str__(self) -> str:
        return "ExternEngroup"

    @classmethod
    def name_no_generic(cls) -> str:
        return "ExternEngroup"

    def new_var(self, compiler):
        return ExternEGroup(compiler)


class ExternEGroupType(EGroupType):
    def __init__(self, compiler: "Compiler"):
        super().__init__(compiler.external_template)
        self.compiler = compiler

    def datatype_hook(self):
        return ExternEGroupDataType(self.compiler)


class _ExternEGroupResolve(ConstExprCombined, ConstructorFunction):
    cdata_type = ctdt_function

    def __init__(self, owner: "ExternEGroup"):
        super().__init__(FunctionDataType())
        self.owner = owner
        self.func_repr = (localize("objects.externegroup.resolve")
                          % self.owner.data_type)

    def initialize(self, instance: "EntityGroup", compiler: "Compiler"):
        SELF = self.owner.get_selector().to_str()
        template = instance.template
        commands = EGroupType(template).initialize(instance, compiler, [], {})
        commands.append(cmds.ScbSetConst(
            cmds.ScbSlot(SELF, compiler.etemplate_id_scb),
            template.runtime_id
        ))
        commands.append("tag %s add %s" % (SELF, instance.tag))
        return commands

    def pre_initialize(self, args: ARGS_T, keywords: KEYWORDS_T, compiler):
        template_out = None

        @axe.chop
        @axe.arg("template", ETemplateDataType)
        def _call_me(compiler, template: "EntityTemplate"):
            nonlocal template_out
            template_out = template

        BinaryFunction(_call_me).call(args, keywords, compiler)
        return EGroupDataType(template_out), {}


class ExternEGroup(EntityGroup):
    def __init__(self, compiler: "Compiler"):
        super().__init__(ExternEGroupDataType(compiler), compiler)
        self.attribute_table.set("resolve", _ExternEGroupResolve(self))
