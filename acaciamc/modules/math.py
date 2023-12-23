"""math - Math related utilities."""
from typing import List

from acaciamc.mccmdgen.expression import *
from acaciamc.mccmdgen.expression.integer import (
    IntRandom, IntOpSelf, IntCmdOp, IntOpVar
)
from acaciamc.ast import ModuleMeta
from acaciamc.tools import axe
import acaciamc.mccmdgen.cmds as cmds

def internal(name: str) -> AcaciaExpr:
    res = _math.attribute_table.lookup(name)
    if res is None:
        raise ValueError(name)
    return res

@axe.chop
@axe.arg("min", axe.LiteralInt(), rename="min_")
@axe.arg("max", axe.LiteralInt(), rename="max_")
def _randint(compiler, min_: int, max_: int):
    """randint(min: int-literal, max: int-literal) -> int
    Get a random integer between `min` and `max` (inclusive).
    """
    return IntOpGroup(init=IntRandom(min_, max_), compiler=compiler)

@axe.chop
@axe.arg("base", IntDataType)
@axe.arg("exp", IntDataType)
def _pow(compiler, base, exp):
    """pow(base: int, exp: int) -> int
    return "base" to the power of "exp".
    `pow(0, 0)` is defined to be 1.
    Negative values of `exp` result in undefined behavior.
    """
    if not isinstance(exp, IntLiteral):
        # Fallback to `_math._pow`
        return internal("_pow").call(args=[base, exp], keywords={})
    if exp.value < 0:
        raise axe.ArgumentError('exp', 'must be a non-negative integer')
    if exp.value == 0:
        return IntLiteral(1, compiler)
    # Optimize when x is a literal
    if isinstance(base, IntLiteral):
        return IntLiteral(base.value ** exp.value, compiler)
    # Write
    res = IntOpGroup.from_intexpr(base)
    for _ in range(exp.value - 1):
        res.add_op(IntOpSelf("*"))
    return res

@axe.chop
@axe.star_arg("operands", IntDataType)
def _min(compiler, operands: List[AcaciaExpr]):
    """min(*operands: int) -> int
    Return the minimum value among `args`.
    """
    if not operands:
        raise axe.ArgumentError('operands', 'at least 1 operand required')
    # Get first arg
    res = IntOpGroup.from_intexpr(operands[0])
    # Handle args left
    for operand in operands[1:]:
        deps, var = to_IntVar(operand)
        res.add_op(IntCmdOp(deps))
        res.add_op(IntOpVar("<", var.slot))
    return res

@axe.chop
@axe.star_arg("operands", IntDataType)
def _max(compiler, operands: List[AcaciaExpr]):
    """max(*operands: int) -> int
    Return the maximum value among `args`.
    """
    if not operands:
        raise axe.ArgumentError('operands', 'at least 1 operand required')
    # Get first arg
    res = IntOpGroup.from_intexpr(operands[0])
    # Handle args left
    for operand in operands[1:]:
        deps, var = to_IntVar(operand)
        res.add_op(IntCmdOp(deps))
        res.add_op(IntOpVar(">", var.slot))
    return res

@axe.chop
@axe.arg("x", IntDataType)
@axe.arg("y", IntDataType)
def _mod(compiler, x, y):
    if isinstance(x, IntLiteral) and isinstance(y, IntLiteral):
        if y.value == 0:
            raise axe.ArgumentError('y', 'modulo by 0')
        return IntLiteral(x.value % y.value, compiler)
    return internal("_mod").call(args=[x, y], keywords={})

@axe.chop
@axe.arg("x", IntDataType)
@axe.arg("y", IntDataType)
def _floordiv(compiler, x, y):
    if isinstance(x, IntLiteral) and isinstance(y, IntLiteral):
        if y.value == 0:
            raise axe.ArgumentError('y', 'cannot divide by 0')
        return IntLiteral(x.value // y.value, compiler)
    return internal("_floordiv").call(args=[x, y], keywords={})

def acacia_build(compiler):
    global _math
    _math = compiler.get_module(ModuleMeta("_math"))
    attrs = {
        'randint': BinaryFunction(_randint, compiler),
        'pow': BinaryFunction(_pow, compiler),
        'min': BinaryFunction(_min, compiler),
        'max': BinaryFunction(_max, compiler),
        'mod': BinaryFunction(_mod, compiler),
        'floordiv': BinaryFunction(_floordiv, compiler),
    }
    attrs.update(_math.attribute_table)
    return attrs
