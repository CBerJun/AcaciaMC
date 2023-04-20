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
            compiler.types.get(BuiltinTypeType, self), compiler
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
    
    def call(self, args, keywords):
        # calling a type is to create an instance
        # which means 2 things:
        # 1. call self.__new__ and get instance
        # 2. call instance.__init__ if exists
        # Call __new__
        new = self.attribute_table.lookup('__new__')
        if new is None:
            self.compiler.error(
                ErrorType.CANT_CREATE_INSTANCE, type_ = self.name
            )
        inst, cmds = new.call(args, keywords)
        # Call initializer of instance if exists
        initializer = inst.attribute_table.lookup('__init__')
        if initializer is not None:
            ret, _cmds = initializer.call(args, keywords)
            if not isinstance(ret.type, BuiltinNoneType):
                self.compiler.error(
                    ErrorType.INITIALIZER_RESULT, type_ = self.name
                )
            cmds.extend(_cmds)
        return inst, cmds

# e.g. the type of "type"
class BuiltinTypeType(Type):
    name = 'type'

class BuiltinIntType(Type):
    name = 'int'
    
    def do_init(self):
        self.attribute_table.set('MAX', IntLiteral(INT_MAX, self.compiler))
        self.attribute_table.set('MIN', IntLiteral(INT_MIN, self.compiler))
        def _new(func: BinaryFunction):
            # `int()` -> literal `0`
            # `int(x: int)` -> x
            # `int(x: bool)` -> 0 if x.value is False else 1
            arg = func.arg_optional(
                'x',
                default = IntLiteral(0, self.compiler),
                type_ = (BuiltinIntType, BuiltinBoolType)
            )
            if isinstance(arg.type, BuiltinIntType):
                return arg
            elif isinstance(arg.type, BuiltinBoolType):
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

class BuiltinBoolType(Type):
    name = 'bool'
    
    def new_var(self, tmp = False):
        objective, selector = self._new_score(tmp)
        return BoolVar(objective, selector, self.compiler)

class BuiltinFunctionType(Type):
    name = 'function'

class BuiltinNoneType(Type):
    name = 'nonetype'

    def new_var(self, tmp = False):
        return NoneVar(self.compiler)

class BuiltinStringType(Type):
    name = 'str'

class BuiltinModuleType(Type):
    name = 'module'

# These imports are for builtin attributes (e.g. int.MAX; int.__new__)
# Import these later to prevent circular import
from .callable import BinaryFunction
from .boolean import BoolVar, BoolLiteral, to_BoolVar
from .integer import IntVar, IntLiteral
from .none import NoneVar

BUILTIN_TYPES = (
    BuiltinTypeType, BuiltinIntType, BuiltinBoolType,
    BuiltinFunctionType, BuiltinNoneType, BuiltinStringType,
    BuiltinModuleType
)

__all__ = [
    # Base class
    'Type',
    # Tuple of builtin types
    'BUILTIN_TYPES'
]
__all__.extend(map(lambda t: t.__name__, BUILTIN_TYPES))
