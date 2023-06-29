"""Values of "type" type in Acacia.
e.g. "int" is a "type".
"""

from typing import Tuple, TYPE_CHECKING, Type as PythonType, Union
try:  # Python 3.8+
    from typing import final
except ImportError:
    def final(func):
        return func

from .base import *
from acaciamc.error import *
from acaciamc.constants import INT_MIN, INT_MAX

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from .entity import _EntityBase
    from .entity_template import EntityTemplate

class Type(AcaciaExpr):
    """Base class for type of a variable that is a type
    (e.g. type of builtin "int" is `IntType`).
    """
    name = None

    @final
    def __init__(self, compiler: "Compiler"):
        """Override `do_init` instead of this."""
        super().__init__(
            DataType.from_type(compiler.types.get(TypeType, self), compiler),
            compiler
        )

    def do_init(self):
        """Initialzer for `Type`s -- override it instead of `__init__`.
        This exists because when compiler is initializing `Type`s,
        it has not stored the type in `compiler.types`. However,
        we might need to use them when initializing (for example,
        to create attributes), so we split `__init__` and `do_init`.
        """
        pass

    def _new_score(self, tmp) -> Tuple[str, str]:
        """Util for method `new_var`, allocate a new score
        return (str<objective>, str<selectore>).
        """
        return (
            self.compiler.allocate_tmp
            if tmp else self.compiler.allocate
        )()

    def new_var(self, tmp=False) -> VarValue:
        """New a `VarValue` of this type.
        Only "storable" types need to implement this.
        When `tmp` set to True, return a temporary value.
        """
        raise NotImplementedError

    def new_entity_field(self) -> dict:
        """When a field of an entity template is this type, this is
        called. This should return a dict of data (which is called
        "field meta") that identifies this field application
        (See `IntType` for an example).
        If this is not defined, this type can't be used as fields.
        `new_var_as_field` should be used together with this.
        """
        raise NotImplementedError

    def new_var_as_field(self, entity: "_EntityBase", **meta) -> VarValue:
        """See `new_entity_field`.
        The `meta` are the same as field meta, and this should
        return the field specified by field meta for `entity`.
        """
        raise NotImplementedError

    def call(self, args, keywords):
        """Calling a type is to create an instance of this type.
        Two things are done:
        1. call `self.__new__` and get `instance`
        2. call `instance.__init__` if exists.
        """
        # Call `__new__`
        new = self.attribute_table.lookup('__new__')
        if new is None:
            self.compiler.error(ErrorType.CANT_CREATE_INSTANCE,
                                type=self.name)
        instance, cmds = new.call(args, keywords)
        # Call initializer of instance if exists
        initializer = instance.attribute_table.lookup('__init__')
        if initializer is not None:
            ret, _cmds = initializer.call(args, keywords)
            if not ret.data_type.raw_matches(NoneType):
                self.compiler.error(ErrorType.INITIALIZER_RESULT,
                                    type_=self.name)
            cmds.extend(_cmds)
        return instance, cmds

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
                default=IntLiteral(0, self.compiler),
                type_=(IntType, BoolType)
            )
            if arg.data_type.raw_matches(IntType):
                return arg
            elif arg.data_type.raw_matches(BoolType):
                if isinstance(arg, BoolLiteral):
                    # Python `int` also converts boolean to integer
                    return IntLiteral(int(arg.value), self.compiler)
                # fallback: convert `arg` to `BoolVar`,
                # Since boolean just use 0 to store False, 1 to store
                # True, just "cast" it to `IntVar`.
                dependencies, bool_var = to_BoolVar(arg)
                return IntVar(
                    objective=bool_var.objective, selector=bool_var.selector,
                    compiler=self.compiler
                ), dependencies
        self.attribute_table.set(
            '__new__', BinaryFunction(_new, self.compiler)
        )

    def new_var(self, tmp=False) -> "IntVar":
        objective, selector = self._new_score(tmp)
        return IntVar(objective, selector, self.compiler)

    def new_entity_field(self):
        return {"scoreboard": self.compiler.add_scoreboard()}

    def new_var_as_field(self, entity, **meta) -> "IntVar":
        return IntVar(meta["scoreboard"], str(entity),
                      self.compiler, with_quote=False)

class BoolType(Type):
    name = 'bool'

    def new_var(self, tmp=False):
        objective, selector = self._new_score(tmp)
        return BoolVar(objective, selector, self.compiler)

    def new_entity_field(self):
        return {"scoreboard": self.compiler.add_scoreboard()}

    def new_var_as_field(self, entity, **meta) -> "BoolVar":
        return BoolVar(meta["scoreboard"], str(entity),
                      self.compiler, with_quote=False)

class FunctionType(Type):
    name = 'function'

class NoneType(Type):
    name = 'nonetype'

    def new_var(self, tmp=False) -> "NoneVar":
        return NoneVar(self.compiler)

class StringType(Type):
    name = 'str'

class ModuleType(Type):
    name = 'module'

class ETemplateType(Type):
    name = 'entity_template'

class EntityType(Type):
    name = 'entity'

    def new_var(self, template: "EntityTemplate", tmp=False):
        var = TaggedEntity.from_empty(template, self.compiler)
        if tmp:
            self.compiler.add_tmp_entity(var)
        return var

class DataType:
    """Data type like `int`, `bool` or entity like `entity(Template)`.
    WHAT'S THE FIFFERENCE BETWEEN `Type` AND THIS?
     `Type` is an expression that represents a type like `int` or
     `entity`. `DataType` specifies the type of an expression
     completely, including template for entity, like `int` or
     `entity(Template)`.
    """
    def __init__(self, type_: Type, is_entity: bool, compiler: "Compiler"):
        """Do not initialize directly, use factory methods."""
        if not isinstance(type_, Type):
            compiler.error(ErrorType.INVALID_TYPE_SPEC, got=type_.name)
        self.type = type_
        self.is_entity = is_entity
        self.template: Union[None, "EntityTemplate"] = None

    @classmethod
    def from_type(cls, type_: Type, compiler: "Compiler"):
        """Generate `DataType` from a `type_`."""
        return cls(type_, is_entity=False, compiler=compiler)

    @classmethod
    def from_type_cls(cls, type_: PythonType[Type], compiler: "Compiler"):
        """Generate `DataType` from `type_` class."""
        return cls(compiler.types[type_], is_entity=False, compiler=compiler)

    @classmethod
    def from_entity(cls, template: "EntityTemplate", compiler: "Compiler"):
        # Generate `DataType` from an entity with given `template`
        inst = cls(compiler.types[EntityType],
                   is_entity=True, compiler=compiler)
        inst.template = template
        return inst

    def __str__(self) -> str:
        if self.is_entity:
            assert self.template
            return "%s(%s)" % (self.type.name, self.template.name)
        else:
            return self.type.name

    def new_var(self, *args, **kwargs) -> AcaciaExpr:
        if self.is_entity:
            assert self.template
            return self.type.new_var(template=self.template, *args, **kwargs)
        else:
            return self.type.new_var(*args, **kwargs)

    def new_entity_field(self, *args, **kwargs):
        return self.type.new_entity_field(*args, **kwargs)

    def new_var_as_field(self, *args, **kwargs):
        return self.type.new_var_as_field(*args, **kwargs)

    def is_type_of(self, expr: AcaciaExpr) -> bool:
        """Return whether `expr` is of this type."""
        return self.matches(expr.data_type)

    def matches(self, type_: "DataType") -> bool:
        """Return whether `type_` is the same type as this type,
        and if `type_` is entity, check whether the template of
        `type_` is a sub-template of this type's template.
        """
        if self.is_entity:
            assert self.template
            return (type_.is_entity and
                    type_.template.is_subtemplate_of(self.template))
        else:
            return isinstance(type_.type, type(self.type))

    def raw_matches(self, type_: PythonType[Type]) -> bool:
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
