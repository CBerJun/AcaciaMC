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
If a class can't handle an operation `self.xxx(other)`, other's method
`other.rxxx(self)` is used.
"""

__all__ = [
    # Type related
    'IntType', 'IntDataType',
    # Expression
    'IntLiteral', 'IntVar', 'IntOpGroup',
    # Utils
    'to_IntVar'
]

from typing import TYPE_CHECKING, List, Tuple, Callable, Optional, Dict, Union
from abc import ABCMeta, abstractmethod
from functools import partialmethod
import operator

from .base import *
from .types import Type
from .boolean import (
    CompareBase, BoolDataType, BoolLiteral, ScbMatchesCompare, to_BoolVar
)
from acaciamc.error import *
from acaciamc.constants import INT_MIN, INT_MAX
from acaciamc.tools import axe, resultlib, cmethod_of
from acaciamc.ast import Operator, COMPOP_INVERT
from acaciamc.mccmdgen.datatype import (
    DefaultDataType, Storable, SupportsEntityField
)
from acaciamc.ctexec.expr import CTDataType
import acaciamc.mccmdgen.cmds as cmds

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.cmds import _ExecuteSubcmd
    from acaciamc.ctexec.expr import CTObj

STR2SCBOP = {
    "+": cmds.ScbOp.ADD_EQ,
    "-": cmds.ScbOp.SUB_EQ,
    "*": cmds.ScbOp.MUL_EQ,
    "/": cmds.ScbOp.DIV_EQ,
    "%": cmds.ScbOp.MOD_EQ,
    "<": cmds.ScbOp.MIN,
    ">": cmds.ScbOp.MAX,
    "=": cmds.ScbOp.ASSIGN
}
STR2METHOD = {
    '+': "add", '-': "sub",
    '*': "mul", '/': "div", '%': "mod"
}
COMPOP2SCBOP = {
    Operator.greater: cmds.ScbCompareOp.GT,
    Operator.greater_equal: cmds.ScbCompareOp.GTE,
    Operator.less: cmds.ScbCompareOp.LT,
    Operator.less_equal: cmds.ScbCompareOp.LTE,
    Operator.equal_to: cmds.ScbCompareOp.EQ
}
COMPOP2PYOP = {
    Operator.equal_to: operator.eq,
    Operator.unequal_to: operator.ne,
    Operator.greater: operator.gt,
    Operator.less: operator.lt,
    Operator.greater_equal: operator.ge,
    Operator.less_equal: operator.le
}

def remainder(a: int, b: int) -> int:
    """C-style % operator, which MC uses."""
    res = abs(a) % abs(b)
    return res if a >= 0 else -res

def c_int_div(a: int, b: int) -> int:
    """C-style / operator, which MC uses."""
    if (a >= 0) != (b >= 0) and a % b:
        return a // b + 1
    else:
        return a // b

STR2PYINTOP: Dict[str, Callable[[int, int], int]] = {
    '+': int.__add__, '-': int.__sub__, '*': int.__mul__,
    '/': c_int_div, '%': remainder
}

class IntDataType(DefaultDataType, Storable, SupportsEntityField):
    name = "int"

    def new_var(self) -> "IntVar":
        return IntVar.new(self.compiler)

    def new_entity_field(self):
        return {"scoreboard": self.compiler.add_scoreboard()}

    def new_var_as_field(self, entity, **meta) -> "IntVar":
        return IntVar(cmds.ScbSlot(entity.to_str(), meta["scoreboard"]),
                      self.compiler)

ctdt_int = CTDataType("int")

class IntType(Type):
    def do_init(self):
        self.attribute_table.set('MAX', IntLiteral(INT_MAX, self.compiler))
        self.attribute_table.set('MIN', IntLiteral(INT_MIN, self.compiler))
        @cmethod_of(self, "__new__")
        @axe.chop
        @axe.arg("b", BoolDataType)
        @axe.slash
        def _new(compiler, b):
            """
            int(b: bool, /) -> int
            Returns 1 if `b` is True, or 0 otherwise.
            """
            if isinstance(b, BoolLiteral):
                return resultlib.literal(int(b.value), compiler)
            # Fallback: convert `b` to `BoolVar`,
            # Since 0 is used to store False, 1 is for True, just
            # "cast" it to `IntVar`.
            dependencies, bool_var = to_BoolVar(b)
            res = IntVar(bool_var.slot, self.compiler)
            res.is_temporary = True
            return res, dependencies

    def datatype_hook(self):
        return IntDataType(self.compiler)

    def cdatatype_hook(self):
        return ctdt_int

class IntCompare(CompareBase):
    """
    A boolean that stores comparison between 2 integer expressions.
    This only stores one comparison, unlike the AST node `CompareOp`,
    so "a > b > 1" is stored in two `IntCompare`s.
    """
    def __init__(
        self, left: AcaciaExpr, operator: Operator,
        right: AcaciaExpr, compiler
    ):
        super().__init__(compiler)
        self.left = left
        self.operator = operator
        self.right = right

    def as_execute(self) -> Tuple[CMDLIST_T, List["_ExecuteSubcmd"]]:
        res_dependencies = []  # return[0]
        res_main = []  # return[1]
        dependency, var_left = to_IntVar(self.left)
        res_dependencies.extend(dependency)
        dependency, var_right = to_IntVar(self.right)
        res_dependencies.extend(dependency)
        # != is specially handled, because Minecraft does not provide
        # such syntax like 'if score ... != ...' while other 5
        # operators are built-in in MC.
        if self.operator is Operator.unequal_to:
            res_main.append(cmds.ExecuteScoreComp(
                var_left.slot, var_right.slot,
                cmds.ScbCompareOp.EQ, invert=True
            ))
        else:  # for other 5 operators
            res_main.append(cmds.ExecuteScoreComp(
                var_left.slot, var_right.slot, COMPOP2SCBOP[self.operator]
            ))
        return res_dependencies, res_main

    # Unary operator
    def unarynot(self):
        return IntCompare(
            self.left, COMPOP_INVERT[self.operator], self.right, self.compiler
        )

class IntLiteral(ConstExprCombined):
    """Represents a literal integer.
    The purpose of these class is to implement constant folding
    which calculate the value of constant expressions
    in compile time (e.g. compiler can convert "2 + 3" to "5").
    """
    cdata_type = ctdt_int

    def __init__(self, value: int, compiler):
        super().__init__(IntDataType(compiler), compiler)
        self.value = value
        # check overflow
        if not INT_MIN <= value <= INT_MAX:
            raise Error(ErrorType.INT_OVERFLOW)

    def cstringify(self) -> str:
        return str(self.value)

    def chash(self):
        return self.value

    def export(self, var: "IntVar"):
        return [cmds.ScbSetConst(var.slot, self.value)]

    def ccompare(self, op, other: Union[AcaciaExpr, "CTObj"]) -> bool:
        if isinstance(other, IntLiteral):
            return COMPOP2PYOP[op](self.value, other.value)
        raise TypeError

    ## UNARY OPERATORS

    def cunarypos(self):
        return self

    def cunaryneg(self):
        return IntLiteral(-self.value, self.compiler)

    ## BINARY OPERATORS

    def _bin_op(self, op: str, other: Union[AcaciaExpr, "CTObj"]):
        if isinstance(other, IntLiteral):
            try:
                v = STR2PYINTOP[op](self.value, other.value)
            except ArithmeticError as err:
                raise Error(ErrorType.CONST_ARITHMETIC, message=str(err))
            return IntLiteral(v, self.compiler)
        raise TypeError

    cadd = partialmethod(_bin_op, '+')
    csub = partialmethod(_bin_op, '-')
    cmul = partialmethod(_bin_op, '*')
    cdiv = partialmethod(_bin_op, '/')
    cmod = partialmethod(_bin_op, '%')

class IntVar(VarValue):
    """An integer variable."""
    def __init__(self, slot: cmds.ScbSlot, compiler):
        super().__init__(IntDataType(compiler), compiler)
        self.slot = slot

    @classmethod
    def new(cls, compiler: "Compiler", tmp=False):
        alloc = compiler.allocate_tmp if tmp else compiler.allocate
        return cls(alloc(), compiler)

    def export(self, var: "IntVar"):
        return [cmds.ScbOperation(cmds.ScbOp.ASSIGN, var.slot, self.slot)]

    def compare(self, op, other):
        if not other.data_type.matches_cls(IntDataType):
            return NotImplemented
        if isinstance(other, IntLiteral):
            return ScbMatchesCompare(
                [], self.slot, op, other.value, self.compiler
            )
        return IntCompare(self, op, other, self.compiler)

    def swap(self, other: "IntVar"):
        return [cmds.ScbOperation(cmds.ScbOp.SWAP, self.slot, other.slot)]

    ## UNARY OPERATORS

    def unarypos(self):
        return self

    def unaryneg(self):
        return IntOpGroup.from_intexpr(self).unaryneg()

    ## BINARY (SELF ... OTHER) OPERATORS

    def _bin_op(self, name: str, other):
        # `name` is method name
        if isinstance(other, (IntLiteral, IntVar)):
            return getattr(IntOpGroup.from_intexpr(self), name)(other)
        raise TypeError

    add = partialmethod(_bin_op, 'add')
    sub = partialmethod(_bin_op, 'sub')
    mul = partialmethod(_bin_op, 'mul')
    div = partialmethod(_bin_op, 'div')
    mod = partialmethod(_bin_op, 'mod')

    ## BINARY (OTHER ... SELF) OPERATORS
    # only `IntLiteral` might call rxxx of self
    # so just convert self to `IntOpGroup` and let this handle operation

    def _r_bin_op(self, name, other):
        if isinstance(other, IntLiteral):
            return getattr(IntOpGroup.from_intexpr(other), name)(self)
        raise TypeError

    radd = partialmethod(_r_bin_op, 'add')
    rsub = partialmethod(_r_bin_op, 'sub')
    rmul = partialmethod(_r_bin_op, 'mul')
    rdiv = partialmethod(_r_bin_op, 'div')
    rmod = partialmethod(_r_bin_op, 'mod')

    # AUGMENTED ASSIGN `ixxx`

    def _iadd_sub(self, other, operator: str) -> list:
        """Implementation of iadd and isub."""
        if isinstance(other, IntLiteral):
            cls = cmds.ScbAddConst if operator == '+' else cmds.ScbRemoveConst
            return [cls(self.slot, other.value)]
        elif isinstance(other, IntVar):
            return [cmds.ScbOperation(
                STR2SCBOP[operator], self.slot, other.slot
            )]
        elif isinstance(other, IntOpGroup):
            return self._aug_IntOpGroup(other, operator)
        raise TypeError

    def _imul_div_mod(self, other, operator: str) -> list:
        """Implementation of imul, idiv, imod."""
        if isinstance(other, IntLiteral):
            const = self.compiler.add_int_const(other.value)
            return [cmds.ScbOperation(
                STR2SCBOP[operator], self.slot, const.slot
            )]
        elif isinstance(other, IntVar):
            return [cmds.ScbOperation(
                STR2SCBOP[operator], self.slot, other.slot
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
        value = getattr(self, STR2METHOD[operator])(other)
        ## Export
        tmp = IntVar.new(self.compiler, tmp=True)
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

class IntOp(metaclass=ABCMeta):
    # This is intended to be immutable
    def scb_did_read(self, slot: cmds.ScbSlot) -> bool:
        # Override-able
        return False

    def scb_did_assign(self, slot: cmds.ScbSlot) -> bool:
        # Override-able
        return False

    @abstractmethod
    def resolve(self, var: IntVar) -> CMDLIST_T:
        # The returned list won't be modified
        pass

class IntSetConst(IntOp):
    def __init__(self, value: int) -> None:
        self.value = value

    def resolve(self, var: IntVar) -> CMDLIST_T:
        return [cmds.ScbSetConst(var.slot, self.value)]

class IntRandom(IntOp):
    def __init__(self, min_: int, max_: int) -> None:
        self.min = min_
        self.max = max_

    def resolve(self, var: IntVar) -> CMDLIST_T:
        return [cmds.ScbRandom(var.slot, self.min, self.max)]

class IntOpConst(IntOp):
    def __init__(self, op: str, value: int) -> None:
        self.op = op
        self.value = value

    def resolve(self, var: IntVar) -> CMDLIST_T:
        if self.op == "+" or self.op == "-":
            cls = cmds.ScbAddConst if self.op == "+" else cmds.ScbRemoveConst
            return [cls(var.slot, self.value)]
        c = var.compiler.add_int_const(self.value)
        return [cmds.ScbOperation(STR2SCBOP[self.op], var.slot, c.slot)]

class IntOpVar(IntOp):
    def __init__(self, op: str, slot: cmds.ScbSlot) -> None:
        self.op = STR2SCBOP[op]
        self.slot = slot

    def scb_did_read(self, slot: cmds.ScbSlot) -> bool:
        return slot == self.slot

    def resolve(self, var: IntVar) -> CMDLIST_T:
        return [cmds.ScbOperation(self.op, var.slot, self.slot)]

class IntSetVar(IntOpVar):
    def __init__(self, slot: cmds.ScbSlot) -> None:
        super().__init__("=", slot)

class IntOpSelf(IntOp):
    def __init__(self, op: str) -> None:
        self.op = op

    def resolve(self, var: IntVar) -> CMDLIST_T:
        return [cmds.ScbOperation(STR2SCBOP[self.op], var.slot, var.slot)]

class IntCmdOp(IntOp):
    def __init__(self, commands: CMDLIST_T) -> None:
        self.commands = commands

    def scb_did_read(self, slot: cmds.ScbSlot) -> bool:
        for c in self.commands:
            if c.scb_did_read(slot):
                return True
        return False

    def scb_did_assign(self, slot: cmds.ScbSlot) -> bool:
        for c in self.commands:
            if c.scb_did_assign(slot):
                return True
        return False

    def resolve(self, var: IntVar) -> CMDLIST_T:
        return self.commands

class IntOpGroup(AcaciaExpr):
    """An `IntOpGroup` stores complex integer operations."""
    def __init__(self, init: Optional[IntOp], compiler):
        super().__init__(IntDataType(compiler), compiler)
        self.ops: List[IntOp] = []
        if init is not None:
            self.ops.append(init)

    @classmethod
    def from_intexpr(cls, init: AcaciaExpr) -> "IntOpGroup":
        if isinstance(init, IntOpGroup):
            return init
        res = cls(None, init.compiler)
        if isinstance(init, IntLiteral):
            res.add_op(IntSetConst(init.value))
        elif isinstance(init, IntVar):
            res.add_op(IntSetVar(init.slot))
        else:
            raise TypeError
        return res

    def export(self, var: IntVar):
        need_tmp = False
        for op in self.ops:
            if op.scb_did_read(var.slot) or op.scb_did_assign(var.slot):
                need_tmp = True
                break
        if need_tmp:
            tmp = IntVar.new(self.compiler, tmp=True)
        else:
            tmp = var
        res = []
        for op in self.ops:
            res.extend(op.resolve(tmp))
        if need_tmp:
            res.extend(tmp.export(var))
        return res

    def copy(self):
        res = IntOpGroup(init=None, compiler=self.compiler)
        res.ops = self.ops.copy()
        return res

    def compare(self, op, other):
        if not other.data_type.matches_cls(IntDataType):
            return NotImplemented
        if isinstance(other, IntLiteral):
            commands, var = to_IntVar(self)
            return ScbMatchesCompare(
                commands, var.slot, op, other.value, self.compiler
            )
        return IntCompare(self, op, other, self.compiler)

    def add_op(self, op: IntOp):
        self.ops.append(op)

    ## UNARY OPERATORS

    def unarypos(self):
        return self

    def unaryneg(self):
        # -expr = expr * (-1)
        return self.mul(self.compiler.add_int_const(-1))

    ## BINARY (SELF ... OTHER) OPERATORS

    def _bin_op(self, operator: str, other):
        """Implements binary operators (see `STR2SCBOP`)."""
        res = self.copy()
        if isinstance(other, IntLiteral):
            res.add_op(IntOpConst(operator, other.value))
        elif isinstance(other, IntVar):
            res.add_op(IntOpVar(operator, other.slot))
        elif isinstance(other, IntOpGroup):
            tmp = IntVar.new(self.compiler, tmp=True)
            res.add_op(IntCmdOp(other.export(tmp)))
            res.add_op(IntOpVar(operator, tmp.slot))
        else:
            raise TypeError
        return res

    add = partialmethod(_bin_op, '+')
    sub = partialmethod(_bin_op, '-')
    mul = partialmethod(_bin_op, '*')
    div = partialmethod(_bin_op, '/')
    mod = partialmethod(_bin_op, '%')

    ## BINARY (OTHER ... SELF) OPERATORS
    # `other` in self.rxxx may be IntLiteral or IntVar

    def _r_add_mul(self, name: str, other):
        # a (+ or *) b is b (+ or *) a
        if isinstance(other, (IntLiteral, IntVar)):
            return getattr(self, name)(other)
        raise TypeError

    def _r_sub_div_mod(self, other, name):
        # Convert `other` to `IntOpGroup` and use this to handle this
        # operation.
        if isinstance(other, (IntLiteral, IntVar)):
            return getattr(IntOpGroup.from_intexpr(other), name)(self)
        raise TypeError

    radd = partialmethod(_r_add_mul, 'add')
    rmul = partialmethod(_r_add_mul, 'mul')
    rsub = partialmethod(_r_sub_div_mod, 'sub')
    rdiv = partialmethod(_r_sub_div_mod, 'div')
    rmod = partialmethod(_r_sub_div_mod, 'mod')

# Utils
def to_IntVar(expr: AcaciaExpr, tmp=True) -> Tuple[CMDLIST_T, IntVar]:
    """Convert any integer expression to a `IntVar` and some commands.
    return[0]: the commands to run
    return[1]: the `IntVar`
    """
    if isinstance(expr, IntVar):
        return [], expr
    else:
        var = IntVar.new(expr.compiler, tmp=tmp)
        return expr.export(var), var
