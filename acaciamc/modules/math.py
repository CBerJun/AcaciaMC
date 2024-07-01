"""math - Math related utilities."""
from typing import List, Optional, TYPE_CHECKING

from acaciamc.ast import ModuleMeta
from acaciamc.constants import INT_MIN, INT_MAX
from acaciamc.localization import localize
from acaciamc.mccmdgen.expr import *
from acaciamc.objects import *
from acaciamc.objects.integer import (
    IntRandom, IntCmdOp, IntOpSelf, IntOpVar, IntOp, STR2SCBOP
)
from acaciamc.tools import axe

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler


def internal(name: str) -> AcaciaExpr:
    res = _math.attribute_table.lookup(name)
    if res is None:
        raise ValueError(name)
    return res


@axe.chop
@axe.arg("min", axe.LiteralInt(), rename="min_")
@axe.arg("max", axe.LiteralInt(), rename="max_")
def _randint(compiler, min_: int, max_: int):
    """
    randint(const min: int, const max: int) -> int
    Get a random integer between `min` and `max` (inclusive).
    """
    return IntOpGroup(init=IntRandom(min_, max_))


class IntXOpSelf(IntOp):
    def __init__(self, x: cmds.ScbSlot, op: str) -> None:
        self.op = op
        self.x = x

    def scb_did_assign(self, slot: cmds.ScbSlot) -> bool:
        return slot == self.x

    def resolve(self, var: IntVar) -> CMDLIST_T:
        return [cmds.ScbOperation(STR2SCBOP[self.op], self.x, var.slot)]


@axe.chop
@axe.arg("base", IntDataType)
@axe.arg("exp", IntDataType)
def _pow(compiler: "Compiler", base, exp):
    """
    pow(base: int, exp: int) -> int
    return "base" to the power of "exp".
    `pow(0, 0)` is defined to be 1.
    Negative values of `exp` result in undefined behavior.
    """
    if not isinstance(exp, IntLiteral):
        # Fallback to `_math.pow`
        return internal("pow").call([base, exp], {}, compiler)
    if exp.value < 0:
        raise axe.ArgumentError('exp', localize("modules.math.pow.negative"))
    if exp.value == 0:
        return IntLiteral(1)
    # Optimize when base is a literal
    if isinstance(base, IntLiteral):
        return IntLiteral(base.value ** exp.value)
    # Base is a variable but exp is a literal
    # Reference: https://en.wikipedia.org/wiki/Exponentiation_by_squaring
    # Section "With constant auxiliary memory"
    res = IntOpGroup.from_intexpr(base)
    e = exp.value
    y: Optional[cmds.ScbSlot] = None
    while e != 1:
        if e % 2:  # x & 1 is in fact slower than x % 2 in Python
            if y is None:
                y = compiler.allocate_tmp()
                res.add_op(IntXOpSelf(y, "="))
            else:
                res.add_op(IntXOpSelf(y, "*"))
        res.add_op(IntOpSelf("*"))
        e //= 2  # x >>= 1 is slower than x //= 2, too
    if y is not None:
        res.add_op(IntOpVar("*", y))
    return res


class IntRestrict(IntOp):
    def __init__(self, value: int, is_upper: bool):
        self.value = value
        self.is_upper = is_upper

    def resolve(self, var: IntVar):
        if ((self.is_upper and self.value == INT_MAX)
                or (not self.is_upper and self.value == INT_MIN)):
            return []
        rng = ((str(self.value + 1) + "..") if self.is_upper
               else ".." + str(self.value - 1))
        return [
            cmds.Execute(
                [cmds.ExecuteScoreMatch(var.slot, rng)],
                cmds.ScbSetConst(var.slot, self.value)
            )
        ]


@axe.chop
@axe.star_arg("operands", IntDataType)
def _min(compiler, operands: List[AcaciaExpr]):
    """
    min(*operands: int) -> int
    Return the minimum value among `args`.
    """
    if not operands:
        raise axe.ArgumentError('operands', localize("modules.math.min.empty"))
    # Get literals
    upper = None
    rest = []
    for operand in operands:
        if isinstance(operand, IntLiteral):
            if upper is None or operand.value < upper:
                upper = operand.value
        else:
            rest.append(operand)
    if not rest:
        return IntLiteral(upper)
    # Get first arg
    res = IntOpGroup.from_intexpr(rest[0])
    # Handle args left
    for operand in rest[1:]:
        deps, var = to_IntVar(operand, compiler)
        res.add_op(IntCmdOp(deps))
        res.add_op(IntOpVar("<", var.slot))
    if upper is not None:
        res.add_op(IntRestrict(upper, is_upper=True))
    return res


@axe.chop
@axe.star_arg("operands", IntDataType)
def _max(compiler, operands: List[AcaciaExpr]):
    """
    max(*operands: int) -> int
    Return the maximum value among `args`.
    """
    if not operands:
        raise axe.ArgumentError('operands', localize("modules.math.max.empty"))
    # Get literals
    lower = None
    rest = []
    for operand in operands:
        if isinstance(operand, IntLiteral):
            if lower is None or operand.value > lower:
                lower = operand.value
        else:
            rest.append(operand)
    if not rest:
        return IntLiteral(lower)
    # Get first arg
    res = IntOpGroup.from_intexpr(rest[0])
    # Handle args left
    for operand in rest[1:]:
        deps, var = to_IntVar(operand, compiler)
        res.add_op(IntCmdOp(deps))
        res.add_op(IntOpVar(">", var.slot))
    if lower is not None:
        res.add_op(IntRestrict(lower, is_upper=False))
    return res


@axe.chop
@axe.arg("x", IntDataType)
@axe.arg("y", IntDataType)
def _mod(compiler, x, y):
    if isinstance(x, IntLiteral) and isinstance(y, IntLiteral):
        if y.value == 0:
            raise axe.ArgumentError('y', localize("modules.math.mod.zero"))
        return IntLiteral(x.value % y.value)
    return internal("mod").call([x, y], {}, compiler)


@axe.chop
@axe.arg("x", IntDataType)
@axe.arg("y", IntDataType)
def _floordiv(compiler, x, y):
    if isinstance(x, IntLiteral) and isinstance(y, IntLiteral):
        if y.value == 0:
            raise axe.ArgumentError(
                'y', localize("modules.math.floordiv.zero")
            )
        return IntLiteral(x.value // y.value)
    return internal("floordiv").call([x, y], {}, compiler)


def acacia_build(compiler: "Compiler"):
    global _math
    f = cmds.MCFunctionFile()
    _math = compiler.get_module(ModuleMeta("_math"), f)
    attributes = {
        'randint': BinaryFunction(_randint),
        'pow': BinaryCTFunction(_pow),
        'min': BinaryCTFunction(_min),
        'max': BinaryCTFunction(_max),
        'mod': BinaryCTFunction(_mod),
        'floordiv': BinaryCTFunction(_floordiv),
    }
    return BuiltModule(attributes, f.commands)
