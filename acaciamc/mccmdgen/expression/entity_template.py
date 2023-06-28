"""Entity template of Acacia."""

import itertools

from .base import *
from ...error import *
from .types import ETemplateType, NoneType, DataType
from .entity import TaggedEntity
from .callable import *
from .string import String

__all__ = ["EntityTemplate"]

class _MethodDispatcher:
    def __init__(self, method_name, compiler):
        self.compiler = compiler
        self.method_name = method_name
        self.bound = []
        self.temp_n_impl = []
        self.result_var = None

    def register(self, template, implementation):
        assert isinstance(implementation, (AcaciaFunction, InlineFunction))
        res_type = implementation.result_var.data_type
        if self.result_var is None:
            self.result_var = res_type.new_var()
        else:
            if not self.result_var.data_type.matches(res_type):
                self.compiler.error(
                    ErrorType.OVERRIDE_RESULT_MISMATCH,
                    got=str(res_type), expect=str(self.result_var.data_type),
                    name=implementation.name
                )
        self.temp_n_impl.append((template, implementation))
        for bound in self.bound:
            bound.add_implementation(template, implementation)

    def register_inherit(self, template, parent):
        # XXX this will repeat the whole code that calls implementation
        impl = parent._orig_methods[self.method_name]
        self.register(template, impl)

    def bind_to(self, entity):
        res = BoundMethodDispatcher(entity, self.method_name,
                                    self.result_var, self.compiler)
        self.bound.append(res)
        for template, implementation in self.temp_n_impl:
            res.add_implementation(template, implementation)
        return res

    def bind_to_cast(self, entity):
        candidates = {}
        mro = entity.cast_template.mro_
        for template, implementation in self.temp_n_impl:
            if template in mro:
                candidates[mro.index(template)] = implementation
        implementation = candidates[min(candidates)]
        return BoundMethod(entity, self.method_name,
                           implementation, self.compiler)

class EntityTemplate(AcaciaExpr):
    def __init__(self, name: str, field_types: dict, field_metas: dict,
                 methods: dict, parents: list, metas: dict, compiler):
        super().__init__(
            DataType.from_type_cls(ETemplateType, compiler), compiler
        )
        self.name = name
        self.parents = parents
        self._orig_metas = {}  # Metas are to be handled below
        self._orig_field_types = field_types
        self._orig_field_metas = field_metas
        self._orig_methods = methods
        self.field_types = {}
        self.field_metas = {}
        # methods: list[tuple[EntityTemplate, dict[str, <method>]]]
        # sorted in MRO order
        self.methods = []
        self.method_dispatchers = {}  # type: dict[str, _MethodDispatcher]
        self.metas = {}
        self.mro_ = [self]  # Method Resolution Order
        # Handle meta
        # We convert meta `AcaciaExpr`s to Python objects here:
        #  `@type`, `@position` are converted to `str`
        for name, meta in metas.items():
            if name not in ("type", "position"):
                self.compiler.error(ErrorType.INVALID_ENTITY_META, meta=name)
            # Both `@type` and `@position` requires literal string
            if not isinstance(meta, String):
                self.compiler.error(ErrorType.ENTITY_META, meta=name,
                                    msg="should be a literal string, got "
                                        '"%s"' % str(meta.data_type))
            self._orig_metas[name] = meta.value
        # Runtime identification tag
        # Mark which template an entity is using at runtime.
        # This tag is added to all entities that uses this template
        # *exactly* (i.e. exclude entities that use subtemplate of
        # `self`). This is added when summoning.
        # (See `entity.TaggedEntity.from_template`)
        self.runtime_tag = self.compiler.allocate_entity_tag()
        # Inherit attributes from parents
        ## MRO: We use the same C3 algorithm as Python.
        merge = []
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
                self.compiler.error(ErrorType.MRO)
        ## Inherit attributes
        # We reverse MRO here because we want the former ones to
        # override latter ones
        for parent in reversed(self.mro_):
            for attr in itertools.chain(field_types, methods):
                if attr in self.field_types:
                    self.compiler.error(ErrorType.ATTR_MULTIPLE_DEFS,
                                        attr=attr)
            self.metas.update(parent._orig_metas)
            self.methods.insert(0, (parent, parent._orig_methods))
            self.field_types.update(parent._orig_field_types)
            self.field_metas.update(parent._orig_field_metas)
        ## Handle methods
        for method, implementation in methods.items():
            for parent in self.mro_:
                if method in parent.method_dispatchers:
                    # 1. `method` is overriding parent's definition
                    disp = parent.method_dispatchers[method]
                    break
            else:  # 2. First definition of `method` (new method)
                disp = _MethodDispatcher(method, self.compiler)
            self.method_dispatchers[method] = disp
            disp.register(self, implementation)
        for parent in self.mro_:
            for method, disp in parent.method_dispatchers.items():
                if method not in self.method_dispatchers:
                    # 3. Inherited but not overrided `method`
                    self.method_dispatchers[method] = disp
                    disp.register_inherit(self, parent)

    def register_entity(self, entity):
        # Register attributes to and initialize an entity
        # whose template is self.
        # Every entities MUST call their template's `register_entity`
        assert entity.template is self
        # Convert the stored `methods` into bound method of `entity`
        if entity.cast_template is None:
            for name, disp in self.method_dispatchers.items():
                bound_method_disp = disp.bind_to(entity)
                entity.attribute_table.set(name, bound_method_disp)
        else:
            for name, disp in entity.cast_template.method_dispatchers.items():
                bound_method = disp.bind_to_cast(entity)
                entity.attribute_table.set(name, bound_method)
        # Convert the stored `fields` to attributes of `entity`
        for name, meta in self.field_metas.items():
            type_ = self.field_types[name]
            entity.attribute_table.set(
                name, type_.new_var_as_field(entity, **meta))

    def call(self, args, keywords):
        # Calling an entity template returns an entity, the arguments
        # are passed to __init__ if it exists
        inst, cmds = TaggedEntity.from_template(self, self.compiler)
        # Call __init__ if it exists
        initializer = inst.attribute_table.lookup("__init__")
        if initializer:
            res, _cmds = initializer.call(args, keywords)
            cmds.extend(_cmds)
            if not res.data_type.raw_matches(NoneType):
                self.compiler.error(ErrorType.INITIALIZER_RESULT,
                                    type_=str(inst.data_type))
        return inst, cmds

    def is_subtemplate_of(self, other) -> bool:
        # Return whether `self` is a subtemplate of `other`. A
        # template itself is considered as a subtemplate of itself.
        # other:EntityTemplate
        if self is other:
            return True
        for parent in self.parents:
            if parent.is_subtemplate_of(other):
                return True
        return False
