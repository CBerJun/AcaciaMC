"""math - Math related utilities."""
from typing import List

from acaciamc.mccmdgen.expression import *
from acaciamc.ast import ModuleMeta
from acaciamc.tools import axe

@axe.chop
@axe.arg("min", axe.LiteralInt(), rename="min_")
@axe.arg("max", axe.LiteralInt(), rename="max_")
def _randintc(compiler, min_: int, max_: int):
    """randintc(min: int-literal, max: int-literal) -> int
    Get a random integer between `min` and `max` (inclusive).
    """
    res = IntOpGroup(init=None, compiler=compiler)
    res.write('scoreboard players random {this} %d %d' % (min_, max_))
    return res

@axe.chop
@axe.arg("base", IntType)
@axe.arg("exp", IntType)
def _pow(compiler, base, exp):
    """pow(base: int, exp: int) -> int
    return "base" to the power of "exp".
    """
    if not isinstance(exp, IntLiteral):
        # Fallback to `_math._pow`
        return _math_pow.call(args=[base, exp], keywords={})
    if exp.value <= 0:
        raise axe.ArgumentError('exp', 'must be a positive integer')
    # Optimize when x is a literal
    if isinstance(base, IntLiteral):
        return IntLiteral(base.value ** exp.value, compiler)
    # Write
    res = IntOpGroup(init=base, compiler=compiler)
    cmds = tuple(
        'scoreboard players operation {this} *= {this}'
        for _ in range(exp.value)
    )
    res.write(*cmds)
    return res

@axe.chop
@axe.star_arg("operands", IntType)
def _min(compiler, operands: List[AcaciaExpr]):
    """min(*operands: int) -> int
    Return the minimum value among `args`.
    """
    if not operands:
        raise axe.ArgumentError('operands', 'at least 1 operand required')
    # Get first arg
    res = IntOpGroup(init=operands[0], compiler=compiler)
    # Handle args left
    for operand in operands[1:]:
        dep, var = to_IntVar(operand)
        res.write(*dep)
        res.write('scoreboard players operation {this} < %s' % var)
    return res

@axe.chop
@axe.star_arg("operands", IntType)
def _max(compiler, operands: List[AcaciaExpr]):
    """max(*operands: int) -> int
    Return the maximum value among `args`.
    """
    if not operands:
        raise axe.ArgumentError('operands', 'at least 1 operand required')
    # Get first arg
    res = IntOpGroup(init=operands[0], compiler=compiler)
    # Handle args left
    for operand in operands[1:]:
        dep, var = to_IntVar(operand)
        res.write(*dep)
        res.write('scoreboard players operation {this} > %s' % var)
    return res

def acacia_build(compiler):
    global _math_pow
    _math = compiler.get_module(ModuleMeta("_math"))
    attrs = {
        'randintc': BinaryFunction(_randintc, compiler),
        'pow': BinaryFunction(_pow, compiler),
        'min': BinaryFunction(_min, compiler),
        'max': BinaryFunction(_max, compiler)
    }
    attrs.update(_math.attribute_table)
    _math_pow = _math.attribute_table.lookup("_pow")
    return attrs
