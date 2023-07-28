"""Builtin integer.

Three types of values are used to represent an Acacia int object:
- IntLiteral: a literal integer like `3` (for const folding)
- IntVar: describe a value stored in a Minecraft score
  which is usually an Acacia variable
- IntOpGroup: describe complicated expressions with operators

Q: WHY NOT just use one class to show everything???
A: With these classes apart, we can design a different operator logic for
   each kind of expression.
    e.g. 1 + 1 can be folded and directly get 2 when IntLiteral is apart.
    e.g. 1 + a can be optimized when IntVar is apart
   So the purpose is to optimize the output

This shows the priority of these classes
IntOpGroup > IntVar > IntLiteral
A class can only handle operation with other objects with lower priority
e.g. Literal can only handle operations with Literal
If a class can't handle an operation `self (operator xxx) other`,
other's method `other.__rxxx__` is used
"""

__all__ = [
    # Type
    'IntType',
    # Expression
    'IntLiteral', 'IntVar', 'IntOpGroup',
    # Utils
    'to_IntVar'
]

from typing import List, Tuple
import operator as builtin_op

from .base import *
from .types import Type, DataType
from .callable import BinaryFunction
from . import boolean
from acaciamc.error import *
from acaciamc.constants import INT_MIN, INT_MAX
from acaciamc.tools import axe, resultlib, method_of

def _to_mcop(operator: str):
    # convert "+" to "add", "-" to "remove"
    if operator == '+': return 'add'
    elif operator == '-': return 'remove'
    raise ValueError

class IntType(Type):
    name = 'int'

    def do_init(self):
        self.attribute_table.set('MAX', IntLiteral(INT_MAX, self.compiler))
        self.attribute_table.set('MIN', IntLiteral(INT_MIN, self.compiler))
        @method_of(self, "__new__")
        class _new(metaclass=axe.OverloadChopped):
            """
            int() -> literal 0
            int(x: int) -> x
            int(x: bool) -> 1 if x else 0
            """
            @axe.overload
            def zero(cls, compiler):
                return resultlib.literal(0, compiler)

            @axe.overload
            @axe.arg("x", IntType)
            def copy(cls, compiler, x):
                return x

            @axe.overload
            @axe.arg("b", boolean.BoolType)
            def from_bool(cls, compiler, b):
                if isinstance(b, boolean.BoolLiteral):
                    return resultlib.literal(int(b.value), compiler)
                # Fallback: convert `b` to `BoolVar`,
                # Since 0 is used to store False, 1 is for True, just
                # "cast" it to `IntVar`.
                dependencies, bool_var = boolean.to_BoolVar(b)
                return IntVar(
                    objective=bool_var.objective, selector=bool_var.selector,
                    with_quote=bool_var.with_quote,
                    compiler=self.compiler
                ), dependencies

    def new_var(self, tmp=False) -> "IntVar":
        objective, selector = self._new_score(tmp)
        return IntVar(objective, selector, self.compiler)

    def new_entity_field(self):
        return {"scoreboard": self.compiler.add_scoreboard()}

    def new_var_as_field(self, entity, **meta) -> "IntVar":
        return IntVar(meta["scoreboard"], str(entity),
                      self.compiler, with_quote=False)

class IntLiteral(AcaciaExpr):
    """Represents a literal integer.
    The purpose of these class is to implement constant folding
    which calculate the value of constant expressions
    in compile time (e.g. compiler can convert "2 + 3" to "5").
    """
    def __init__(self, value: int, compiler):
        super().__init__(DataType.from_type_cls(IntType, compiler), compiler)
        self.value = value
        # check overflow
        if not INT_MIN <= value <= INT_MAX:
            raise Error(ErrorType.INT_OVERFLOW)

    def cmdstr(self) -> str:
        return str(self.value)

    def export(self, var: "IntVar"):
        return ['scoreboard players set %s %s' % (var, self)]

    def copy(self):
        return IntLiteral(self.value, self.compiler)

    def __str__(self):
        return str(self.value)

    ## UNARY OPERATORS

    def __pos__(self):
        return self

    def __neg__(self):
        res = self.copy()
        res.value = -res.value
        return res

    ## BINARY OPERATORS

    def _bin_op(self, other, name):
        if isinstance(other, IntLiteral):
            # just calculate `self.value` and `other.value`
            res = self.copy()
            try:
                res.value = getattr(res.value, name)(other.value)
            except ArithmeticError as err:
                raise Error(ErrorType.CONST_ARITHMETIC, message=str(err))
            return res
        return NotImplemented

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
    """An integer variable."""
    def __init__(self, objective: str, selector: str,
                 compiler, with_quote=True):
        super().__init__(DataType.from_type_cls(IntType, compiler), compiler)
        self.objective = objective
        self.selector = selector
        self.with_quote = with_quote

    def export(self, var: "IntVar"):
        return ['scoreboard players operation %s = %s' % (var, self)]

    def __str__(self):
        msg = '"%s" "%s"' if self.with_quote else '%s "%s"'
        return msg % (self.selector, self.objective)

    ## UNARY OPERATORS

    def __pos__(self):
        return self

    def __neg__(self):
        return -IntOpGroup(self, self.compiler)

    ## BINARY (SELF ... OTHER) OPERATORS

    def _bin_op(self, other, name: str):
        # `name` is method name
        if isinstance(other, (IntLiteral, IntVar)):
            res = IntOpGroup(self, self.compiler)
            return getattr(res, name)(other)
        return NotImplemented

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
    # only `IntLiteral` might call __rxxx__ of self
    # so just convert self to `IntOpGroup` and let this handle operation

    def _r_bin_op(self, other, name):
        if isinstance(other, IntLiteral):
            return getattr(IntOpGroup(other, self.compiler), name)(self)
        return NotImplemented

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

    def _iadd_sub(self, other, operator: str) -> list:
        """Implementation of iadd and isub."""
        if isinstance(other, IntLiteral):
            return ['scoreboard players %s %s %s' % (
                _to_mcop(operator), self, other
            )]
        elif isinstance(other, IntVar):
            return ['scoreboard players operation %s %s= %s' % (
                self, operator, other
            )]
        elif isinstance(other, IntOpGroup):
            return self._aug_IntOpGroup(other, operator)
        raise TypeError

    def _imul_div_mod(self, other, operator: str) -> list:
        """Implementation of imul, idiv, imod."""
        if isinstance(other, IntLiteral):
            const = self.compiler.add_int_const(other.value)
            return ['scoreboard players operation %s %s= %s' % (
                self, operator, const
            )]
        elif isinstance(other, IntVar):
            return ['scoreboard players operation %s %s= %s' % (
                self, operator, other
            )]
        elif isinstance(other, IntOpGroup):
            return self._aug_IntOpGroup(other, operator)
        raise TypeError

    def _aug_IntOpGroup(self, other: "IntOpGroup", operator: str):
        """Implementation for augmented assigns where `other` is
        `IntOpGroup`. `operator` is "+", "-", etc.
        """
        # In this condition, we convert a (op)= b to a = a (op) b
        ## Calculate
        value = {
            '+': builtin_op.add, '-': builtin_op.sub,
            '*': builtin_op.mul, '/': builtin_op.floordiv, '%': builtin_op.mod
        }[operator](self, other)
        ## Export
        tmp = self.data_type.new_var(tmp=True)
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

class IntOpGroup(AcaciaExpr):
    """An `IntOpGroup` stores how an integer is changed by storing
    unformatted commands where the target positions of scores are
    preserved. It does not care about which score the value is assigning
    to, but cares about the value itself, until you `export` it, when
    all commands are completed.
    e.g. IntOpGroup `1 + a` might be saved like this:
      scoreboard players set {this} 1
      # (When variable `a` is stored in `acacia1` of scoreboard `acacia`)
      scoreboard players operation {this} += "acacia1" "acacia"
    When method `export` is called, value of "this" is given

    Sometimes temporary scores are needed, those are stored in attribute
    `libs`, where other `IntOpGroup`s are stored (recursively).
    """
    def __init__(self, init, compiler):
        super().__init__(DataType.from_type_cls(IntType, compiler), compiler)
        self.main: List[str] = []
        self.libs: List[IntOpGroup]= []
        self._current_lib_index = 0  # always equals to `len(self.libs)`
        # Initial value
        if isinstance(init, IntLiteral):
            self.write('scoreboard players set {this} %s' % init)
        elif isinstance(init, IntVar):
            self.write('scoreboard players operation {this} = %s' % init)
        elif init is not None:
            raise ValueError

    @export_need_tmp
    def export(self, var: IntVar):
        res = []
        # subvars: Allocate a tmp int for every `IntOpGroup` in
        # `self.libs` and export them to this var; finally format
        # `self.main` using them ({x} means value of self.libs[x]).
        subvars: List[IntVar] = []
        for subexpr in self.libs:
            subvar = self.data_type.new_var(tmp=True)
            subvars.append(subvar)
            res.extend(subexpr.export(subvar))
        res.extend(cmd.format(*subvars, this=var)
                   for cmd in self.main)
        return res

    def _add_lib(self, lib: "IntOpGroup") -> int:
        """Register a dependency and return its index in `self.libs`."""
        self.libs.append(lib)
        self._current_lib_index += 1
        return self._current_lib_index - 1

    def write(self, *commands: str):
        """Write commands."""
        self.main.extend(commands)

    def copy(self):
        res = IntOpGroup(init=None, compiler=self.compiler)
        res.main.extend(self.main)
        res.libs.extend(self.libs)
        res._current_lib_index = self._current_lib_index
        return res

    ## UNARY OPERATORS

    def __pos__(self):
        return self

    def __neg__(self):
        # -expr = expr * (-1)
        neg1 = self.compiler.add_int_const(-1)
        return self * neg1

    ## BINARY (SELF ... OTHER) OPERATORS

    def _add_sub(self, other, operator: str):
        """Implementation of __add__ and __sub__
        `operator` is '+' or '-'.
        """
        res = self.copy()
        if isinstance(other, IntLiteral):
            res.write('scoreboard players %s {this} %s' % (
                _to_mcop(operator), other
            ))
        elif isinstance(other, IntVar):
            res.write('scoreboard players operation {this} %s= %s' % (
                operator, other
            ))
        elif isinstance(other, IntOpGroup):
            res.write('scoreboard players operation {this} %s= {%d}' % (
                operator, res._add_lib(other)
            ))
        else:
            return NotImplemented
        return res

    def _mul_div_mod(self, other, operator: str):
        """Implementation of __mul__, __floordiv__ and __mod__
        operator is '*' or '/' or '%'.
        """
        res = self.copy()
        if isinstance(other, IntLiteral):
            const = self.compiler.add_int_const(other.value)
            res.write('scoreboard players operation {this} %s= %s' % (
                operator, const
            ))
        elif isinstance(other, IntVar):
            res.write('scoreboard players operation {this} %s= %s' % (
                operator, other
            ))
        elif isinstance(other, IntOpGroup):
            res.write('scoreboard players operation {this} %s= {%d}' % (
                operator, res._add_lib(other)
            ))
        else:
            return NotImplemented
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
        if isinstance(other, (IntLiteral, IntVar)):
            return getattr(self, name)(other)
        return NotImplemented

    def _r_sub_div_mod(self, other, name):
        # Convert `other` to `IntOpGroup` and use this to handle this
        # operation.
        if isinstance(other, (IntLiteral, IntVar)):
            return getattr(IntOpGroup(other, self.compiler), name)(self)
        return NotImplemented

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

# Utils
def to_IntVar(expr: AcaciaExpr) -> Tuple[List[str], IntVar]:
    """Convert any integer expression to a `IntVar` and some commands.
    return[0]: the commands to run
    return[1]: the `IntVar`
    """
    if isinstance(expr, IntVar):
        return [], expr
    else:
        tmp = expr.data_type.new_var(tmp=True)
        return expr.export(tmp), tmp
