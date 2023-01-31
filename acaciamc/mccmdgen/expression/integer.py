# Int objects in Acacia
from .base import *
from .types import BuiltinIntType
from ...error import *
from ...constants import INT_MIN, INT_MAX

from copy import deepcopy
import operator as builtin_op

__all__ = [
    # Expression
    'IntLiteral', 'IntVar', 'IntOpGroup', 'IntCallResult',
    # Utils
    'to_IntVar'
]

# Small util

def _to_mcop(operator: str):
    # convert "+" to "add", "-" to "remove"
    if operator == '+': return 'add'
    elif operator == '-': return 'remove'
    raise ValueError

# Four types of values are used to represent an Acacia int object:
# - IntLiteral: a literal integer like `3` (for const folding)
# - IntVar: describe a value stored in a Minecraft score
#   which is usually an Acacia variable
# - IntCallResult: result value of a function that returns int
#   This is quite similar to an IntVar, because result value is stored
#   in an IntVar; this class just adds some dependencies to call the function
# - IntOpGroup: describe complicated expressions with operators

# Q: WHY NOT just use one class to show everything???
# A: With these classes apart, we can design a different operator logic for
#    each kind of expression.
#     e.g. 1 + 1 can be folded and directly get 2 when IntLiteral is apart.
#     e.g. 1 + a can be optimized when IntVar is apart
#    So the purpose is to optimize the output

# This shows the priority of these classes
# IntOpGroup > IntCallResult = IntVar > IntLiteral
# A class can only handle operation with other objects with lower priority
# e.g. Literal can only handle operations with Literal
# If a class can't handle an operation `self (operator xxx) other`,
# other's method `other.__rxxx__` is used

class IntLiteral(AcaciaExpr):
    # Represents a literal integer.
    # NOTE the purpose of these class is to implement an optimization called
    # "constant folding" which calculate the value of constant expressions
    # while compiling (e.g. compiler can convert 2 + 3 to 5)
    def __init__(self, value: int, compiler):
        super().__init__(compiler.types[BuiltinIntType], compiler)
        self.value = value
        # check overflow
        if not INT_MIN <= value <= INT_MAX:
            self.compiler.error(ErrorType.INT_OVERFLOW, value = value)

    def export(self, var):
        # export literal value to var
        return ['scoreboard players set %s %s' % (var, self)]
    
    def deepcopy(self):
        # copy self to another var
        return IntLiteral(value = self.value, compiler = self.compiler)
    
    def __str__(self):
        # return str(literal)
        return str(self.value)

    ## UNARY OPERATORS

    def __pos__(self):
        return self
    
    def __neg__(self):
        res = self.deepcopy()
        res.value = - res.value
        return res
    
    ## BINARY OPERATORS

    def _bin_op(self, other, name):
        if isinstance(other, IntLiteral):
            # just calculate self.value and other.value
            res = self.deepcopy()
            res.value = getattr(res.value, name)(other.value)
            return res
        elif isinstance(other, (IntOpGroup, IntVar, IntCallResult)):
            return NotImplemented
        raise TypeError
    
    def __add__(self, other):
        return self._bin_op(other, '__add__')
    def __sub__(self, other):
        return self._bin_op(other, '__sub__')
    def __mul__(self, other):
        return self._bin_op(other, '__mul__')
    def __floordiv__(self, other):
        return self._bin_op(other, '__floordiv__')
    def __mod__(self, other):
        return self._bin_op(other, '__mod__')

class IntVar(VarValue):
    # an integer variable
    def __init__(
        self, objective: str, selector: str, compiler, with_quote = True
    ):
        # with_quote:bool whether to add quote to selector
        super().__init__(compiler.types[BuiltinIntType], compiler)
        self.objective = objective
        self.selector = selector
        self.with_quote = with_quote
    
    def export(self, var):
        # export self to an IntVar
        # var:IntVar
        return ['scoreboard players operation %s = %s' % (var, self)]

    def __str__(self):
        msg = '"%s" "%s"' if self.with_quote else '%s "%s"'
        return msg % (self.selector, self.objective)
    
    ## UNARY OPERATORS

    def __pos__(self):
        # positive value of an int is itself
        return self
    
    def __neg__(self):
        return -IntOpGroup(self, compiler = self.compiler)
    
    ## BINARY (SELF ... OTHER) OPERATORS

    def _bin_op(self, other, name):
        # implementation of all binary operators
        # name is method name
        if isinstance(other, IntOpGroup):
            # VarValues can't handle Exprs
            return NotImplemented # var.expr -> expr.__rxxx__
        elif isinstance(other, (IntLiteral, IntVar, IntCallResult)):
            res = IntOpGroup(self, compiler = self.compiler)
            return getattr(res, name)(other)
        raise TypeError
    
    def __add__(self, other):
        return self._bin_op(other, '__add__')
    def __sub__(self, other):
        return self._bin_op(other, '__sub__')
    def __mul__(self, other):
        return self._bin_op(other, '__mul__')
    def __floordiv__(self, other):
        return self._bin_op(other, '__floordiv__')
    def __mod__(self, other):
        return self._bin_op(other, '__mod__')
    
    ## BINARY (OTHER ... SELF) OPERATORS
    # only Literal might call __rxxx__ of self
    # so just convert self to Expr and let this Expr handle operation

    def _r_bin_op(self, other, name):
        if isinstance(other, IntLiteral):
            return getattr(
                IntOpGroup(other, compiler = self.compiler), name
            )(self)
        raise TypeError
    
    def __radd__(self, other):
        return self._r_bin_op(other, '__add__')
    def __rsub__(self, other):
        return self._r_bin_op(other, '__sub__')
    def __rmul__(self, other):
        return self._r_bin_op(other, '__mul__')
    def __rfloordiv__(self, other):
        return self._r_bin_op(other, '__floordiv__')
    def __rmod__(self, other):
        return self._r_bin_op(other, '__mod__')
    
    # AUGMENTED ASSIGN `ixxx`
    # directly return a list of commands that change value of self

    def _iadd_sub(self, other, operator: str) -> list:
        # implementation of iadd and isub
        if isinstance(other, IntLiteral):
            return ['scoreboard players %s %s %s' % (
                _to_mcop(operator), self, other
            )]
        elif isinstance(other, IntVar):
            return ['scoreboard players operation %s %s= %s' % (
                self, operator, other
            )]
        elif isinstance(other, IntCallResult):
            res = deepcopy(other.dependencies)
            res.extend(self._iadd_sub(other.result_var, operator))
            return res
        elif isinstance(other, IntOpGroup):
            return self._aug_IntOpGroup(other, operator = operator)
        raise TypeError
    
    def _imul_div_mod(self, other, operator: str) -> list:
        # implementation of imul, idiv, imod
        if isinstance(other, IntLiteral):
            const = self.compiler.add_int_const(other.value)
            return ['scoreboard players operation %s %s= %s' % (
                self, operator, const
            )]
        elif isinstance(other, IntVar):
            return ['scoreboard players operation %s %s= %s' % (
                self, operator, other
            )]
        elif isinstance(other, IntCallResult):
            res = deepcopy(other.dependencies)
            res.extend(self._imul_div_mod(other.result_var, operator))
            return res
        elif isinstance(other, IntOpGroup):
            return self._aug_IntOpGroup(other, operator)
        raise TypeError
    
    def _aug_IntOpGroup(self, other, operator: str) -> list:
        # implementation for augmented assigns where other is IntOpGroup
        # other:IntOpGroup
        # operator:str '+', '-', etc.
        # in this condition, a (op)= b equals to a = a (op) b
        ## Calculate
        value = {
            '+': builtin_op.add, '-': builtin_op.sub,
            '*': builtin_op.mul, '/': builtin_op.floordiv, '%': builtin_op.mod
        }[operator](self, other)
        ## Export
        tmp = self.type.new_var(tmp = True)
        res = value.export(tmp)
        res.extend(tmp.export(self))
        return res
    
    def iadd(self, other):
        return self._iadd_sub(other, '+')
    def isub(self, other):
        return self._iadd_sub(other, '-')
    def imul(self, other):
        return self._imul_div_mod(other, '*')
    def idiv(self, other):
        return self._imul_div_mod(other, '/')
    def imod(self, other):
        return self._imul_div_mod(other, '%')

class IntCallResult(CallResult):
    # Return value of a function that returns int
    def __init__(self, dependencies: list, result_var: IntVar, compiler):
        super().__init__(
            dependencies, result_var,
            compiler.types[BuiltinIntType], compiler
        )
    
    @classmethod
    def _init_class(cls):
        # See base class `CallResult`
        # this method build operator methods; What operator methods do is:
        # Upgrade self to an IntOpGroup and use it to do operation
        def _handle(name):
            # name is method name (e.g. __add__)
            def _wrapped(self, *args, **kwargs):
                res = IntOpGroup(self, compiler = self.compiler)
                res = getattr(res, name)(*args, **kwargs)
                return res
            return _wrapped
        for name in (
            # __pos__ can be optimized so it is not here
            '__neg__',
            '__add__', '__sub__', '__mul__', '__floordiv__', '__mod__',
            '__radd__', '__rsub__', '__rmul__', '__rfloordiv__', '__rmod__'
        ):
            setattr(cls, name, _handle(name))

    def __pos__(self): return self

class IntOpGroup(AcaciaExpr):
    # An IntOpGroup stores how an integer is changed by storing
    # unformatted commands where the target positions of scores are preserved.
    # (It does not care which score the value is assigning to, but cares the
    # value itself, until you `export` it, where all commands are completed)
    # e.g. IntOpGroup `1 + a` might be saved like this:
    #   scoreboard players set {this} 1
    #   # (When variable `a` is stored in `acacia1` of scoreboard `acacia`)
    #   scoreboard players operation {this} += "acacia1" "acacia"
    # when using method `export`, value of "this" is given
    
    # To be more specific, it provides interfaces to change the value
    # Sometimes temporary scores are needed, those are stored in attribute
    # `libs`, where other IntOpGroups are stored (recursively)
    def __init__(self, init, compiler):
        super().__init__(compiler.types[BuiltinIntType], compiler)
        self.main = [] # list[str] (commands)
        self.libs = [] # list[IntOpGroup] (dependencies)
        self._current_lib_index = 0 # always equals to len(self.libs)
        # init value
        if isinstance(init, IntLiteral):
            self.write('scoreboard players set {this} %s' % init)
        elif isinstance(init, IntVar):
            self.write('scoreboard players operation {this} = %s' % init)
        elif isinstance(init, IntCallResult):
            self.write(
                *init.dependencies,
                'scoreboard players operation {this} = %s' % init
            )
        elif init is not None:
            raise ValueError
    
    def export(self, var: IntVar) -> list:
        # export expression and assign value of this expression to `var`
        # return tuple of commands
        res = []
        # subvars:list[IntVar] Allocate a tmp int for every IntOpGroups
        # in self.libs and export them to this var;
        # finally format self.main with them ({x} means value of self.libs[x])
        subvars = []
        for subexpr in self.libs:
            subvar = self.type.new_var(tmp = True)
            subvars.append(subvar)
            res.extend(subexpr.export(subvar))
        res.extend(map(lambda s: s.format(*subvars, this = var), self.main))
        return res
    
    def export_novalue(self):
        # XXX here export_novalue just use export,
        # so redundant commands might be generated
        return self.export(self.type.new(tmp = True))
    
    def _add_lib(self, lib) -> int:
        # register a dependency (which is also an Expr)
        # return its index in self.libs
        # NOTE value of libs are stored in list so in commands {x} will be
        # formatted as value of self.libs[x] when exported
        # lib:Expr
        self.libs.append(lib)
        self._current_lib_index += 1
        return self._current_lib_index - 1
    
    def write(self, *commands: str, pos: int = None):
        # write commands
        # if pos is None, write to self.main; else to libs[pos]
        if pos is None:
            target = self.main
        else:
            target = self.libs[pos]
        target.extend(commands)
    
    def deepcopy(self):
        # deepcopy this `IntOpGroup`
        # NOTE some of the attributes are not deepcopied
        res = IntOpGroup(init = None, compiler = self.compiler)
        res.main = deepcopy(self.main)
        res.libs = deepcopy(self.libs)
        res._current_lib_index = self._current_lib_index
        return res

    ## UNARY OPERATORS

    def __pos__(self):
        # +expr = expr
        return self
    
    def __neg__(self):
        # -expr = expr * (-1)
        neg1 = self.compiler.add_int_const(-1)
        return self * neg1
    
    ## BINARY (SELF ... OTHER) OPERATORS

    def _add_sub(self, other, operator):
        # implementation of __add__ and __sub__
        # operator is '+' or '-'
        res = self.deepcopy()
        if isinstance(other, IntLiteral):
            res.write('scoreboard players %s {this} %s' % (
                _to_mcop(operator), other
            ))
        elif isinstance(other, IntVar):
            res.write('scoreboard players operation {this} %s= %s' % (
                operator, other
            ))
        elif isinstance(other, IntCallResult):
            res.write(*other.dependencies)
            res = res._add_sub(other.result_var, operator)
        elif isinstance(other, IntOpGroup):
            res.write('scoreboard players operation {this} %s= {%d}' % (
                operator, res._add_lib(other)
            ))
        else:
            raise TypeError
        return res
    
    def _mul_div_mod(self, other, operator: str):
        # implementation of __mul__, __div__ and __mod__
        # operator is '*' or '/' or '%'
        res = self.deepcopy()
        if isinstance(other, IntLiteral):
            const = self.compiler.add_int_const(other.value)
            res.write('scoreboard players operation {this} %s= %s' % (
                operator, const
            ))
        elif isinstance(other, IntVar):
            res.write('scoreboard players operation {this} %s= %s' % (
                operator, other
            ))
        elif isinstance(other, IntCallResult):
            res.write(*other.dependencies)
            res = res._mul_div_mod(other.result_var, operator)
        elif isinstance(other, IntOpGroup):
            res.write('scoreboard players operation {this} %s= {%d}' % (
                operator, res._add_lib(other)
            ))
        else:
            raise TypeError
        return res
    
    def __add__(self, other):
        return self._add_sub(other, '+')
    def __sub__(self, other):
        return self._add_sub(other, '-')
    def __mul__(self, other):
        return self._mul_div_mod(other, '*')
    def __floordiv__(self, other):
        return self._mul_div_mod(other, '/')
    def __mod__(self, other):
        return self._mul_div_mod(other, '%')

    ## BINARY (OTHER ... SELF) OPERATORS
    # `other` in self.__rxxx__ may be Literal or VarValue

    def _r_add_mul(self, other, name):
        # a (+ or *) b is b (+ or *) a
        if isinstance(other, (IntLiteral, IntVar, IntCallResult)):
            return getattr(self, name)(other)
        raise TypeError
    
    def _r_sub_div_mod(self, other, name):
        # convert `other` to Expr and use that Expr to handle this operation
        if isinstance(other, (IntLiteral, IntVar, IntCallResult)):
            return getattr(
                IntOpGroup(other, compiler = self.compiler), name
            )(self)
        raise TypeError
    
    def __radd__(self, other):
        return self._r_add_mul(other, '__add__')
    def __rsub__(self, other):
        return self._r_sub_div_mod(other, '__sub__')
    def __rmul__(self, other):
        return self._r_add_mul(other, '__mul__')
    def __rfloordiv__(self, other):
        return self._r_sub_div_mod(other, '__floordiv__')
    def __rmod__(self, other):
        return self._r_sub_div_mod(other, '__mod__')

# --- Utils ---

def to_IntVar(expr: AcaciaExpr):
    # make any int expr become an IntVar,
    # with the dependencies and var apart
    # expr:IntVar|IntOpGroup|IntLiteral
    # return[0]: the dependency to calculate the operand itself
    # return[1]: the final IntVar that is used
    if isinstance(expr, IntVar):
        return (), expr
    elif isinstance(expr, IntCallResult):
        return tuple(expr.dependencies), expr.result_var
    else:
        tmp = expr.type.new_var(tmp = True)
        return expr.export(tmp), tmp
