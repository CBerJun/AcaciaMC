# vars of "type" type in Acacia
# (e.g. type of builtin `int`)
from .base import *
from ...error import *
from ...constants import INT_MIN, INT_MAX

class Type(AcaciaExpr):
    # type of a variable that is a type (e.g. type of builtin `int`)
    name = None

    def __init__(self, compiler):
        # decide type (type of Type is Type)
        # NOTE DO NOT OVERRIDE THIS __init__!!!
        # USE `DO_INIT` BELOW INSTAEAD
        super().__init__(
            DataType.from_type(compiler.types.get(TypeType, self), compiler),
            compiler
        )
    
    def do_init(self):
        # initialzer for Types; use it instead of __init__
        # this exists because when compiler is initializing Types,
        # it has not stored the type in compiler.types; However,
        # we might need to use them when initializing (for example,
        # to create attributes)
        # so we split `__init__` and `do_init`
        pass
    
    def _new_score(self, tmp):
        # Util for method `new`, allocate a new field
        # return (str<objective>, str<selectore>)
        return (
            self.compiler.allocate_tmp if tmp \
            else self.compiler.allocate
        )()
    
    def new_var(self, tmp = False) -> VarValue:
        # new a VarValue of self type
        # this is not implemented by every subclasses,
        # only types that has got its kind of VarValue needs to implement
        # this method. (e.g. builtin `int` has IntVar, so it has `new_var`)
        # tmp: return a tmp var if True
        raise NotImplementedError
    
    def new_entity_field(self) -> dict:
        # When a field of an entity template uses self type, this is
        # called. This should return a dict of data (which is called
        # "field meta") that identify this field application
        # (See BuiltinIntType for an example).
        # If this is not defined, self type can't be used as fields.
        # NOTE `new_var_as_field` should be used together with this
        raise NotImplementedError
    
    def new_var_as_field(self, entity, **meta) -> VarValue:
        # See `new_entity_field`.
        # The `kwargs` are the same as field meta, and this should
        # return the field specified by field meta for `entity`
        raise NotImplementedError
    
    def call(self, args, keywords):
        # calling a type is to create an instance
        # which means 2 things:
        # 1. call self.__new__ and get instance
        # 2. call instance.__init__ if exists
        # Call __new__
        new = self.attribute_table.lookup('__new__')
        if new is None:
            self.compiler.error(ErrorType.CANT_CREATE_INSTANCE,
                                type=self.name)
        inst, cmds = new.call(args, keywords)
        # Call initializer of instance if exists
        initializer = inst.attribute_table.lookup('__init__')
        if initializer is not None:
            ret, _cmds = initializer.call(args, keywords)
            if not ret.data_type.raw_matches(NoneType):
                self.compiler.error(ErrorType.INITIALIZER_RESULT,
                                    type_=self.name)
            cmds.extend(_cmds)
        return inst, cmds

# e.g. the type of "type"
class TypeType(Type):
    name = 'type'

class IntType(Type):
    name = 'int'
    
    def do_init(self):
        self.attribute_table.set('MAX', IntLiteral(INT_MAX, self.compiler))
        self.attribute_table.set('MIN', IntLiteral(INT_MIN, self.compiler))
        def _new(func: BinaryFunction):
            # `int()` -> literal `0`
            # `int(x: int)` -> x
            # `int(x: bool)` -> 1 if x.value else 0
            arg = func.arg_optional(
                'x',
                default = IntLiteral(0, self.compiler),
                type_ = (IntType, BoolType)
            )
            if arg.data_type.raw_matches(IntType):
                return arg
            elif arg.data_type.raw_matches(BoolType):
                # True -> 1; False -> 0
                if isinstance(arg, BoolLiteral):
                    # Python int(bool) also converts boolean to integer
                    return IntLiteral(int(arg.value), self.compiler)
                # fallback: convert `arg` to BoolVar,
                # NOTE since boolean just use 0 to store False,
                # 1 to store True, just "cast" it to IntVar
                dependencies, bool_var = to_BoolVar(arg)
                return IntVar(
                    objective=bool_var.objective, selector=bool_var.selector,
                    compiler=self.compiler
                ), dependencies
        self.attribute_table.set(
            '__new__', BinaryFunction(_new, self.compiler)
        )
    
    def new_var(self, tmp = False):
        objective, selector = self._new_score(tmp)
        return IntVar(objective, selector, self.compiler)

    def new_entity_field(self) -> dict:
        return {"scoreboard": self.compiler.add_scoreboard()}
    
    def new_var_as_field(self, entity, **meta):
        return IntVar(meta["scoreboard"], str(entity),
                      self.compiler, with_quote=False)

class BoolType(Type):
    name = 'bool'
    
    def new_var(self, tmp = False):
        objective, selector = self._new_score(tmp)
        return BoolVar(objective, selector, self.compiler)

    def new_entity_field(self) -> dict:
        return {"scoreboard": self.compiler.add_scoreboard()}

    def new_var_as_field(self, entity, **meta):
        return BoolVar(meta["scoreboard"], str(entity),
                      self.compiler, with_quote=False)

class FunctionType(Type):
    name = 'function'

class NoneType(Type):
    name = 'nonetype'

    def new_var(self, tmp = False):
        return NoneVar(self.compiler)

class StringType(Type):
    name = 'str'

class ModuleType(Type):
    name = 'module'

class ETemplateType(Type):
    name = 'entity_template'

class EntityType(Type):
    name = 'entity'

    def new_var(self, template, tmp=False):
        # template:EntityTemplate
        var = TaggedEntity.from_empty(template, self.compiler)
        if tmp:
            self.compiler.add_tmp_entity(var)
        return var

class DataType:
    # Can be types like `int`, `bool` or entity like `entity(Template)`
    # WHAT'S THE FIFFERENCE BETWEEN `Type` AND THIS?
    #  `Type` is an expression that represents a type like `int` or
    #  `entity`. `DataType` specifies the type of an expression
    #  completely, including template for entity, like `int` or
    #  `entity(Template)`.
    def __init__(self, type_: Type, is_entity: bool, compiler):
        # NOTE Do not call this, use factories below
        if not isinstance(type_, Type):
            compiler.error(ErrorType.INVALID_TYPE_SPEC, got=type_.name)
        self.type = type_
        self.is_entity = is_entity

    @classmethod
    def from_type(cls, type_: Type, compiler):
        # Generate `SpecifiedType` from a `type_`
        return cls(type_, is_entity=False, compiler=compiler)

    @classmethod
    def from_type_cls(cls, type_: type, compiler):
        # Generate `SpecifiedType` from the class of a `type_`
        # type_:subclass of `Type`
        return cls(compiler.types[type_], is_entity=False, compiler=compiler)

    @classmethod
    def from_entity(cls, template, compiler):
        # Generate `SpecifiedType` from an entity
        # with given `template`
        inst = cls(compiler.types[EntityType],
                   is_entity=True, compiler=compiler)
        inst.template = template
        return inst

    def __str__(self) -> str:
        if self.is_entity:
            return "%s(%s)" % (self.type.name, self.template.name)
        else:
            return self.type.name

    def new_var(self, *args, **kwargs) -> AcaciaExpr:
        # Return a new var of this type
        if self.is_entity:
            return self.type.new_var(template=self.template, *args, **kwargs)
        else:
            return self.type.new_var(*args, **kwargs)
    
    def new_entity_field(self, *args, **kwargs):
        return self.type.new_entity_field(*args, **kwargs)

    def new_var_as_field(self, *args, **kwargs):
        return self.type.new_var_as_field(*args, **kwargs)

    def is_type_of(self, expr: AcaciaExpr) -> bool:
        # Return whether `expr` is of this type
        return self.matches(expr.data_type)

    def matches(self, type_) -> bool:
        # Return whether `type_` is the same type as this type,
        # and if `type_` is entity, check whether the template of
        # `type_` is a sub-template of this type's template.
        # type_:DataType
        if self.is_entity:
            return (type_.is_entity and
                    type_.template.is_subtemplate_of(self.template))
        else:
            return isinstance(type_.type, type(self.type))

    def raw_matches(self, type_: type) -> bool:
        # type_:subclass of `Type` or tuple of them
        return isinstance(self.type, type_)

# These imports are for builtin attributes (e.g. int.MAX; int.__new__)
# Import these later to prevent circular import
from .callable import BinaryFunction
from .boolean import BoolVar, BoolLiteral, to_BoolVar
from .integer import IntVar, IntLiteral
from .none import NoneVar
from .entity import TaggedEntity

BUILTIN_TYPES = (
    TypeType, IntType, BoolType, FunctionType, NoneType, StringType,
    ModuleType, ETemplateType, EntityType
)

__all__ = [
    # Base class
    'Type',
    # Tuple of builtin types
    'BUILTIN_TYPES',
    # Data type
    'DataType'
]
__all__.extend(map(lambda t: t.__name__, BUILTIN_TYPES))
