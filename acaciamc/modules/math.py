"""math - Math related utilities."""
from acaciamc.mccmdgen.expression import *
from acaciamc.ast import ModuleMeta

def _randintc(func: BinaryFunction):
    """randintc(min: int-literal, max: int-literal) -> int
    Get a random integer between `min` and `max` (inclusive).
    """
    # Parse arg
    arg_min = func.arg_require('min', IntType)
    arg_max = func.arg_require('max', IntType)
    func.assert_no_arg()
    if not isinstance(arg_min, IntLiteral):
        func.arg_error('min', 'must be a constant')
    if not isinstance(arg_max, IntLiteral):
        func.arg_error('max', 'must be a constant')
    # Write
    res = IntOpGroup(init=None, compiler=func.compiler)
    res.write('scoreboard players random {this} %s %s' % (arg_min, arg_max))
    return res

def _pow(func: BinaryFunction):
    """pow(x: int, y: int) -> int
    return x to the power of y.
    """
    # Parse args
    arg_x = func.arg_require('x', IntType)
    arg_y = func.arg_require('y', IntType)
    func.assert_no_arg()
    if not isinstance(arg_y, IntLiteral):
        # Fallback to `_math._pow`
        return _math_pow.call(args=[arg_x, arg_y], keywords={})
    if arg_y.value <= 0:
        func.arg_error('y', 'must be a positive integer')
    # Special handle when x is a literal
    if isinstance(arg_x, IntLiteral):
        return IntLiteral(arg_x.value ** arg_y.value, func.compiler)
    # Write
    res = IntOpGroup(init=arg_x, compiler=func.compiler)
    cmds = tuple(
        'scoreboard players operation {this} *= {this}'
        for _ in range(arg_y.value)
    )
    res.write(*cmds)
    return res

def _min(func: BinaryFunction):
    """min(*args:int) -> int
    Return the minimum value among `args`.
    """
    # Parse args
    args, arg_kw = func.arg_raw()
    if arg_kw:
        raise Error(ErrorType.ANY, '"min" does not receive keyword arguments')
    if not args:
        raise Error(ErrorType.ANY, '"min" needs at least 1 argument')
    for arg in args:
        if not arg.data_type.raw_matches(IntType):
            raise Error(ErrorType.ANY, '"min" arguments should all be int')
    # Calculate
    ## get first arg
    res = IntOpGroup(args[0], func.compiler)
    ## handle args left
    for arg in args[1:]:
        dep, var = to_IntVar(arg)
        res.write(*dep)
        res.write('scoreboard players operation {this} < %s' % var)
    return res

def _max(func: BinaryFunction):
    """max(*args:int) -> int
    Return the maximum value among `args`.
    """
    # Parse args
    args, arg_kw = func.arg_raw()
    if arg_kw:
        raise Error(ErrorType.ANY, '"max" does not receive keyword arguments')
    if not args:
        raise Error(ErrorType.ANY, '"max" needs at least 1 argument')
    for arg in args:
        if not arg.data_type.raw_matches(IntType):
            raise Error(ErrorType.ANY, '"max" arguments should all be int')
    # Calculate
    ## get first arg
    res = IntOpGroup(args[0], func.compiler)
    ## handle args left
    for arg in args[1:]:
        dep, var = to_IntVar(arg)
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
