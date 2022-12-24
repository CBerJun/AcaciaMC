# the builtin `math` module of Acacia
from acaciamc.mccmdgen.expression import *

def _randintc(func: BinaryFunction):
    # randintc(min: int-literal, max: int-literal) -> int
    # get a random integer between [`min`, `max`]
    # Parse arg
    arg_min = func.arg_require('min', BuiltinIntType)
    arg_max = func.arg_require('max', BuiltinIntType)
    func.assert_no_arg()
    if not isinstance(arg_min, IntLiteral):
        func.arg_error('min', 'must be a constant')
    if not isinstance(arg_max, IntLiteral):
        func.arg_error('max', 'must be a constant')
    # Write
    res = IntOpGroup(init = None, compiler = func.compiler)
    res.write('scoreboard players random {this} %s %s' % (arg_min, arg_max))
    return res

def _powc(func: BinaryFunction):
    # powc(x: int, y: int-literal) -> int
    # return x to the power of y
    # Parse args
    arg_x = func.arg_require('x', BuiltinIntType)
    arg_y = func.arg_require('y', BuiltinIntType)
    func.assert_no_arg()
    if not isinstance(arg_y, IntLiteral):
        func.arg_error('y', 'must be a constant')
    if arg_y.value <= 0:
        func.arg_error('y', 'must be a positive integer')
    # Special handle when x is a literal
    if isinstance(arg_x, IntLiteral):
        return IntLiteral(arg_x.value ** arg_y.value, func.compiler)
    # Write
    res = IntOpGroup(init = arg_x, compiler = func.compiler)
    cmds = tuple(
        'scoreboard players operation {this} *= {this}' \
        for _ in range(arg_y.value)
    )
    res.write(*cmds)
    return res

def _min(func: BinaryFunction):
    # min(*args:int) -> int
    # return the minimum value between `args`
    # Parse args
    args, arg_kw = func.arg_raw()
    if arg_kw:
        func.compiler.error(
            ErrorType.ANY, '"min" does not receive keyword arguments'
        )
    if not args:
        func.compiler.error(ErrorType.ANY, '"min" needs at least 1 argument')
    for arg in args:
        if not isinstance(arg.type, BuiltinIntType):
            func.compiler.error(
                ErrorType.ANY, '"min" arguments should all be int'
            )
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
    # max(*args:int) -> int
    # return the maximum value between `args`
    # Parse args
    args, arg_kw = func.arg_raw()
    if arg_kw:
        func.compiler.error(
            ErrorType.ANY, '"max" does not receive keyword arguments'
        )
    if not args:
        func.compiler.error(ErrorType.ANY, '"max" needs at least 1 argument')
    for arg in args:
        if not isinstance(arg.type, BuiltinIntType):
            func.compiler.error(
                ErrorType.ANY, '"max" arguments should all be int'
            )
    # Calculate
    ## get first arg
    res = IntOpGroup(args[0], func.compiler)
    ## handle args left
    for arg in args[1:]:
        dep, var = to_IntVar(arg)
        res.write(*dep)
        res.write('scoreboard players operation {this} > %s' % var)
    return res

# TODO add function `min` and `max`
# TODO add function `pow(int, int) -> loop`

def acacia_build(compiler):
    return {
        'randintc': BinaryFunction(_randintc, compiler),
        'powc': BinaryFunction(_powc, compiler),
        'min': BinaryFunction(_min, compiler),
        'max': BinaryFunction(_max, compiler)
    }
