"""math - Math related utilities."""
from typing import List
from itertools import repeat

from acaciamc.mccmdgen.expression import *
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
    res = IntOpGroup(init=None, compiler=compiler)
    res.write(lambda this, libs: cmds.ScbRandom(this, min_, max_))
    return res

@axe.chop
@axe.arg("base", IntDataType)
@axe.arg("exp", IntDataType)
def _pow(compiler, base, exp):
    """pow(base: int, exp: int) -> int
    return "base" to the power of "exp".
    """
    if not isinstance(exp, IntLiteral):
        # Fallback to `_math._pow`
        return internal("_pow").call(args=[base, exp], keywords={})
    if exp.value <= 0:
        raise axe.ArgumentError('exp', 'must be a positive integer')
    # Optimize when x is a literal
    if isinstance(base, IntLiteral):
        return IntLiteral(base.value ** exp.value, compiler)
    # Write
    res = IntOpGroup(init=base, compiler=compiler)
    res.write(*repeat(
        lambda this, libs: cmds.ScbOperation(cmds.ScbOp.MUL_EQ, this, this),
        exp.value
    ))
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
    res = IntOpGroup(init=operands[0], compiler=compiler)
    # Handle args left
    def _handle(operand):
        deps, var = to_IntVar(operand)
        res.write_str(*deps)
        res.write(lambda this, libs:
                  cmds.ScbOperation(cmds.ScbOp.MIN, this, var.slot))
    for operand in operands[1:]:
        _handle(operand)
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
    res = IntOpGroup(init=operands[0], compiler=compiler)
    # Handle args left
    def _handle(operand):
        deps, var = to_IntVar(operand)
        res.write_str(*deps)
        res.write(lambda this, libs:
                  cmds.ScbOperation(cmds.ScbOp.MAX, this, var.slot))
    for operand in operands[1:]:
        _handle(operand)
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
