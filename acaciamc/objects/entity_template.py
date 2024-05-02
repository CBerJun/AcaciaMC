"""Entity template of Acacia."""

__all__ = ["ETemplateDataType", "EntityTemplate"]

from typing import (
    List, Tuple, Dict, Union, Any, Optional, Callable, TYPE_CHECKING
)
import itertools

from acaciamc.ast import MethodQualifier
from acaciamc.error import *
from acaciamc.mccmdgen.datatype import DefaultDataType, Storable
from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.utils import unreachable
from .entity import TaggedEntity, EntityDataType
from .functions import (
    BoundVirtualMethod, BoundMethod, InlineFunction, ConstructorFunction
)
from .string import String
from .none import NoneDataType
from .position import Position
from .spawn_info import SpawnInfoDataType

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.datatype import SupportsEntityField
    from .functions import METHODDEF_T
    from .entity import _EntityBase

class ETemplateDataType(DefaultDataType):
    name = 'entity_template'

ctdt_etemplate = CTDataType("entity_template")

class _MethodDispatcher:
    """
    Every virtual method and methods that override it share one
    `_MethodDispatcher`.
    """
    def __init__(self, method_name: str, compiler: "Compiler"):
        self.compiler = compiler
        self.method_name = method_name
        self.bound: List[BoundVirtualMethod] = []
        self.impls: Dict[
            "METHODDEF_T",
            Tuple[List["EntityTemplate"], Optional[Callable[[], TaggedEntity]]]
        ] = {}
        self.result_var: Union[VarValue, None] = None

    def register(self, template: "EntityTemplate",
                 implementation: "METHODDEF_T"):
        res_type = implementation.result_type
        assert isinstance(res_type, Storable)
        if self.result_var is None:
            self.result_var = res_type.new_var(self.compiler)
        else:
            if not self.result_var.data_type.matches(res_type):
                raise Error(
                    ErrorType.OVERRIDE_RESULT_MISMATCH,
                    got=str(res_type), expect=str(self.result_var.data_type),
                    name=implementation.name
                )
        if isinstance(implementation, InlineFunction):
            get_self_var = None
        else:
            _sv = None
            def get_self_var():
                nonlocal _sv
                if _sv is None:
                    _sv = TaggedEntity.new_tag(template, self.compiler)
                return _sv
        self.impls[implementation] = ([template], get_self_var)
        for bound in self.bound:
            bound.add_implementation(template, implementation, get_self_var)

    def register_inherit(self, template: "EntityTemplate",
                         parent: "EntityTemplate"):
        for impl, (templates, get_self) in self.impls.items():
            if parent in templates:
                templates.append(template)
                for bound in self.bound:
                    bound.add_implementation(template, impl, get_self)
                break
        else:
            unreachable("Base not found")

    def bind_to(self, entity: "_EntityBase"):
        res = BoundVirtualMethod(
            entity, self.method_name, self.result_var, self.compiler
        )
        self.bound.append(res)
        for impl, (templates, get_self_var) in self.impls.items():
            for template in templates:
                res.add_implementation(template, impl, get_self_var)
        return res

    def bind_to_cast(self, entity: "_EntityBase"):
        best = None
        mro = entity.cast_template.mro_
        for impl, (templates, get_self_var) in self.impls.items():
            try:
                i = mro.index(templates[0])
            except ValueError:
                pass
            else:
                if best is None or i < best[0]:
                    best = i, impl, get_self_var
        _, impl, get_self_var = best
        return BoundMethod(entity, self.method_name, impl, get_self_var)

class _SimpleMethod:
    """Non-virtual and non-override methods."""
    def __init__(self, name: str, implementation: "METHODDEF_T",
                 template: "EntityTemplate", compiler: "Compiler"):
        self.name = name
        self.compiler = compiler
        self.implementation = implementation
        self.template = template
        self.is_inline = isinstance(implementation, InlineFunction)
        self._self_var = None

    def get_self_var(self) -> TaggedEntity:
        # We don't compute this inside __init__ because at that time
        # the template is not fully initialized yet.
        assert not self.is_inline
        if self._self_var is None:
            self._self_var = TaggedEntity.new_tag(self.template, self.compiler)
        return self._self_var

    def bind_to(self, entity: "_EntityBase"):
        return BoundMethod(
            entity, self.name, self.implementation,
            None if self.is_inline else self.get_self_var,
        )

def _check_override(implementation: "METHODDEF_T", method: str):
    """
    Check if `implementation` can be used as virtual method or
    override a virtual method.
    """
    if isinstance(implementation, InlineFunction):
        res_type = implementation.result_type
        if not isinstance(res_type, Storable):
            raise Error(ErrorType.OVERRIDE_RESULT_UNSTORABLE,
                        name=method, type_=str(res_type))

class EntityTemplate(ConstExprCombined, ConstructorFunction):
    cdata_type = ctdt_etemplate

    def __init__(self, name: str,
                 field_types: Dict[str, "SupportsEntityField"],
                 field_metas: Dict[str, dict],
                 methods: Dict[str, AcaciaCallable],
                 method_qualifiers: Dict[str, MethodQualifier],
                 parents: List["EntityTemplate"],
                 compiler: "Compiler",
                 source=None):
        super().__init__(ETemplateDataType())
        self.name = name
        self.func_repr = self.name
        if source is not None:
            self.source = source
        self.parents = parents
        self._orig_field_types = field_types
        self._orig_field_metas = field_metas
        self.field_types: Dict[str, "SupportsEntityField"] = {}
        self.field_metas: Dict[str, dict] = {}
        # method_dispatchers: for virtual methods AND override methods
        self.method_dispatchers: Dict[str, _MethodDispatcher] = {}
        self.simple_methods: Dict[str, _SimpleMethod] = {}
        self.static_methods: Dict[str, AcaciaCallable] = {}
        self.mro_: List[EntityTemplate] = [self]  # Method Resolution Order
        # Runtime identification tag
        # Mark which template an entity is using at runtime.
        # This tag is added to all entities that uses this template
        # *exactly* (i.e. exclude entities that use subtemplate of
        # `self`). This is added when summoning.
        # (See `entity.TaggedEntity.summon_new`)
        self.runtime_tag = compiler.allocate_entity_tag()
        # Inherit attributes from parents
        ## MRO: We use the same C3 algorithm as Python.
        merge: List[List[EntityTemplate]] = []
        for parent in self.parents:
            if parent.mro_:
                merge.append(parent.mro_.copy())
        if self.parents:
            merge.append(self.parents.copy())
        while merge:
            for ts in merge.copy():
                candidate = ts[0]
                for ts2 in merge:
                    if candidate in ts2[1:]:
                        break
                else:
                    self.mro_.append(candidate)
                    for ts3 in merge.copy():
                        if candidate in ts3:
                            ts3.remove(candidate)
                            if not ts3:
                                merge.remove(ts3)
                    break
            else:
                raise Error(ErrorType.MRO)
        ## Inherit attributes
        # We reverse MRO here because we want the former ones to
        # override latter ones
        for parent in reversed(self.mro_):
            for attr in itertools.chain(field_types, methods):
                if attr in self.field_types:
                    raise Error(ErrorType.EFIELD_MULTIPLE_DEFS, attr=attr)
            self.field_types.update(parent._orig_field_types)
            self.field_metas.update(parent._orig_field_metas)
        ## Handle methods
        for method, implementation in methods.items():
            qualifier = method_qualifiers[method]
            for parent in self.mro_:
                if method in parent.method_dispatchers:
                    if qualifier is MethodQualifier.override:
                        # This method is overriding a virtual method
                        _check_override(implementation, method)
                        disp = parent.method_dispatchers[method]
                        self.method_dispatchers[method] = disp
                        disp.register(self, implementation)
                        break
                    else:
                        # This method is overriding a virtual method but
                        # did not use `override` qualifier. Complain.
                        raise Error(ErrorType.OVERRIDE_QUALIFIER,
                                    name=method, got=qualifier.value)
                if (
                    method in parent.simple_methods
                    and qualifier is MethodQualifier.static
                ):
                    # This static method tries to override an
                    # instance method
                    raise Error(ErrorType.STATIC_OVERRIDE_INST, name=method)
                if (
                    method in parent.static_methods
                    and qualifier is not MethodQualifier.static
                ):
                    # This instance method tries to override a static
                    # method
                    raise Error(ErrorType.INST_OVERRIDE_STATIC, name=method)
            else:
                if qualifier is MethodQualifier.none:
                    # This method is a simple method
                    self.simple_methods[method] = _SimpleMethod(
                        method, implementation, self, compiler
                    )
                elif qualifier is MethodQualifier.virtual:
                    # This method is a virtual method
                    _check_override(implementation, method)
                    disp = _MethodDispatcher(method, compiler)
                    self.method_dispatchers[method] = disp
                    disp.register(self, implementation)
                elif qualifier is MethodQualifier.override:
                    # This method is marked as override, but actually
                    # did not override any virtual method. Complain.
                    raise Error(ErrorType.NOT_OVERRIDING, name=method)
                else:
                    assert qualifier is MethodQualifier.static
                    # This method is a static method
                    self.static_methods[method] = implementation
        fields_got = frozenset(itertools.chain(
            self.method_dispatchers, self.simple_methods, self.static_methods
        ))
        for parent in self.mro_:
            for method, disp in parent.method_dispatchers.items():
                if method not in fields_got:
                    # Inherited override methods
                    self.method_dispatchers[method] = disp
                    disp.register_inherit(self, parent)
            for method, mgr in parent.simple_methods.items():
                if method not in fields_got:
                    # Inherited simple methods
                    self.simple_methods[method] = mgr
            for method, impl in parent.static_methods.items():
                if method not in fields_got:
                    # Inherited static methods
                    self.static_methods[method] = impl
        ## Register static methods to attribute table
        for name, impl in self.static_methods.items():
            self.attribute_table.set(name, impl)

    def datatype_hook(self):
        return EntityDataType(self)

    def register_entity(self, entity: "_EntityBase"):
        # Register attributes to and initialize an entity
        # whose template is self.
        # Every entities MUST call their template's `register_entity`
        assert entity.template is self
        # Convert stored virtual methods into bound method of `entity`.
        if entity.cast_template is None:
            for name, disp in self.method_dispatchers.items():
                entity.attribute_table.set(name, disp.bind_to(entity))
        else:
            for name, disp in entity.cast_template.method_dispatchers.items():
                entity.attribute_table.set(name, disp.bind_to_cast(entity))
        # Convert stored simple methods into bound method of `entity`.
        if entity.cast_template is None:
            template = self
        else:
            template = entity.cast_template
        for name, mgr in template.simple_methods.items():
            entity.attribute_table.set(name, mgr.bind_to(entity))
        # Convert stored fields to attributes of `entity`.
        for name, meta in self.field_metas.items():
            type_ = self.field_types[name]
            entity.attribute_table.set(
                name, type_.new_var_as_field(entity, **meta)
            )
        # Add static methods
        for name, impl in template.static_methods.items():
            entity.attribute_table.set(name, impl)

    def initialize(self, instance: "_EntityBase", args, keywords, compiler):
        """
        Calling an entity template summons a new entity, the arguments
        are passed to __spawn__ and __init__ if they exist.
        """
        location = f"<entity constructor of {self.name}>"
        commands = []
        info = None
        # Call __spawn__
        spawn = instance.template.attribute_table.lookup("__spawn__")
        if spawn is not None:
            if not isinstance(spawn, AcaciaCallable):
                raise Error(ErrorType.SPAWN_NOT_CALLABLE,
                            got=str(spawn.data_type),
                            type_=str(instance.data_type))
            info, _cmds = spawn.call_withframe(
                args, keywords, compiler, location
            )
            commands.extend(_cmds)
            if not info.data_type.matches_cls(SpawnInfoDataType):
                raise Error(ErrorType.SPAWN_RESULT,
                            got=str(info.data_type),
                            type_=str(instance.data_type))
        # Create instance
        _, _cmds = TaggedEntity.summon_new(self, compiler, instance, info)
        commands.extend(_cmds)
        # Call __init__
        initializer = instance.attribute_table.lookup("__init__")
        if initializer:
            if not isinstance(initializer, AcaciaCallable):
                raise Error(ErrorType.INITIALIZER_NOT_CALLABLE,
                            got=str(initializer.data_type),
                            type_=str(instance.data_type))
            res, _cmds = initializer.call_withframe(
                args, keywords, compiler, location
            )
            commands.extend(_cmds)
            if not res.data_type.matches_cls(NoneDataType):
                raise Error(ErrorType.INITIALIZER_RESULT,
                            type_=str(instance.data_type))
        return commands

    def is_subtemplate_of(self, other: "EntityTemplate") -> bool:
        # Return whether `self` is a subtemplate of `other`. A
        # template itself is considered as a subtemplate of itself.
        if self is other:
            return True
        for parent in self.parents:
            if parent.is_subtemplate_of(other):
                return True
        return False
