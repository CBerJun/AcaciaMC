# Generate commands of bool expressions
from .base import *
from .integer import *
from .types import BuiltinIntType, BuiltinBoolType
from ...ast import Operator
from ...error import *
from ...constants import INT_MAX, INT_MIN

from copy import deepcopy
from functools import reduce
import operator as builtin_op

__all__ = [
    # Expressions
    'BoolLiteral', 'BoolVar', 'NotBoolVar', 'BoolCompare', 'AndGroup',
    # Factory functions
    'new_compare', 'new_and_group', 'new_or_expression',
    # Utils
    'to_BoolVar'
]

# There are several classes that are used to represent bool expressions:
# - BoolLiteral: Boolean literal (True or False)
# - BoolVar: Boolean Acacia variable
#   NOTE when score == 1, it's True; == 0, it's False
#   Although 1 bit is enough for a boolean, we still use a whole
#   score (int) to store bool, bacause spliting a bit from a score costs
#   much commands.
# - NotBoolVar: inverted (`not var`) form of BoolVar
# - BoolCompare: store comparison between 2 integer expressions
#   NOTE this only store ONE comparison (unlike the AST node CompareOp)
#   e.g. a > b > 1 is stored in 2 BoolCompares
#   NOTE always use factory method `new_compare`
# - AndGroup: store several bool expressions that are connected with `and`
#   NOTE always use factory method `new_and_group`

# NOTE Q: WHERE IS AN `or` EXPRESSION STORED???
# A: `or` expressions are all converted into other types of expressions
# this is done by `new_or_expression`

class BoolLiteral(AcaciaExpr):
    def __init__(self, value: bool, compiler):
        super().__init__(compiler.types[BuiltinBoolType], compiler)
        self.value = value
    
    def export(self, var):
        # export self to a BoolVar
        return ['scoreboard players set %s %s' % (var, self)]
    
    def deepcopy(self):
        # copy self to another var
        return BoolLiteral(value = self.value, compiler = self.compiler)
    
    def __str__(self):
        # return '1' if True, else '0'
        return str(int(self.value))
    
    # --- UNARY OP ---
    def not_(self):
        res = self.deepcopy()
        res.value = not res.value
        return res

class BoolVar(VarValue):
    def __init__(self, objective: str, selector: str, compiler):
        super().__init__(compiler.types[BuiltinBoolType], compiler)
        self.objective = objective
        self.selector = selector
    
    def __str__(self):
        return '"%s" "%s"' % (self.selector, self.objective)

    def export(self, var) -> list:
        # var:BoolVar
        return ['scoreboard players operation %s = %s' % (var, self)]
        
    # --- UNARY OP ---
    def not_(self):
        return NotBoolVar(
            self.objective, self.selector,
            compiler = self.compiler
        )

class NotBoolVar(AcaciaExpr):
    def __init__(self, objective: str, selector: str, compiler):
        super().__init__(compiler.types[BuiltinBoolType], compiler)
        self.objective = objective
        self.selector = selector
    
    def __str__(self):
        return '"%s" "%s"' % (self.selector, self.objective)
    
    def export(self, var: BoolVar):
        return [
            'scoreboard players set %s 0' % var,
            export_execute_subcommands(
                subcmds = ['if score %s matches 0' % self],
                main = 'scoreboard players set %s 1' % var
            )
        ]
    
    # --- UNARY OP ---
    def not_(self):
        return BoolVar(
            self.objective, self.selector,
            compiler = self.compiler
        )

class BoolCompare(AcaciaExpr):
    def __init__(
        self, left: AcaciaExpr, operator: Operator,
        right: AcaciaExpr, compiler
    ):
        # The factory method is `new_compare` below!
        super().__init__(compiler.types[BuiltinBoolType], compiler)
        self.left = left
        self.operator = operator
        self.right = right
        ## make sure operands are available
        lt, rt = left.type, right.type
        if not (
            isinstance(lt, BuiltinIntType) and
            isinstance(rt, BuiltinIntType)
        ):
            compiler.error(
                ErrorType.INVALID_OPERAND,
                operator = {
                    Operator.greater: '>',
                    Operator.greater_equal: '>=',
                    Operator.less: '<',
                    Operator.less_equal: '<=',
                    Operator.equal_to: '==',
                    Operator.unequal_to: '!='
                }[operator],
                operand = '%r, %r' % (lt.name, rt.name)
            )
        ## NOTE if one of self.left and self.right is IntLiteral,
        ## always make sure that IntLiteral on the right
        ## e.g. `0 < a` -> `a > 0`
        if isinstance(self.left, IntLiteral):
            self.left, self.right = self.right, self.left
            self.operator = {
                Operator.greater: Operator.less,
                Operator.greater_equal: Operator.less_equal,
                Operator.less: Operator.greater,
                Operator.less_equal: Operator.greater_equal,
                Operator.equal_to: Operator.equal_to,
                Operator.unequal_to: Operator.unequal_to
            }[self.operator]
    
    def export(self, var: BoolVar):
        # set `res` to dependencies that as_execute returns
        res, subcmds = self.as_execute()
        # set target to 0 (False) first
        res.append('scoreboard players set %s 0' % var)
        # check condition and change it to 1 (True)
        res.append(export_execute_subcommands(
            subcmds, 'scoreboard players set %s 1' % var
        ))
        return res
    
    def deepcopy(self):
        return BoolCompare(
            self.left, self.operator, self.right,
            compiler = self.compiler
        )
    
    def as_execute(self):
        # convert self to some dependency commands (return[0]:list) and
        # subcommands of /execute (return[1]:list)
        res_dependencies = [] # return[0]
        res_main = [] # return[1]
        # remember that if one of left and right is IntLiteral
        # it will be put on the right (in self.__init__)?
        if isinstance(self.right, IntLiteral):
            literal = self.right.value
            # parse the other operand (that is not IntLiteral)
            dependency, var = to_IntVar(self.left)
            # and write dependency
            res_dependencies.extend(dependency)
            # then write main (according to operator)
            # != is special: it needs 'unless ...' rather than 'if ...'
            if self.operator is Operator.unequal_to:
                res_main.append(
                    'unless score %s matches %d' % (var, literal)
                )
            else: # for other 5 operators
                # get range
                match_range = {
                    Operator.greater: '%d..' % (literal + 1),
                    Operator.greater_equal: '%d..' % literal,
                    Operator.less: '..%d' % (literal - 1),
                    Operator.less_equal: '..%d' % literal,
                    Operator.equal_to: str(literal)
                }[self.operator]
                res_main.append('if score %s matches %s' % (var, match_range))
        else: # if there is no literal: not `if score ... matches` optimization
            # then both operands should be processed
            dependency, var_left = to_IntVar(self.left)
            res_dependencies.extend(dependency)
            dependency, var_right = to_IntVar(self.right)
            res_dependencies.extend(dependency)
            # != is special handled, because Minecraft does not provide
            # such syntax like 'if score ... != ...'
            # while other 5 operators are allowed (e.g. 'if score ... >= ...')
            if self.operator is Operator.unequal_to:
                res_main.append('unless score %s = %s' % (var_left, var_right))
            else: # for other 5 operators
                mcop = {
                    Operator.greater: '>',
                    Operator.greater_equal: '>=',
                    Operator.less: '<',
                    Operator.less_equal: '<=',
                    # NOTE in Minecraft equal_to IS "=" instead of "=="
                    Operator.equal_to: '='
                }[self.operator]
                res_main.append('if score %s %s %s' % (
                    var_left, mcop, var_right
                ))
        return res_dependencies, res_main
    
    # --- UNARY OP ---
    def not_(self):
        res = self.deepcopy()
        res.operator = {
            Operator.greater: Operator.less_equal,
            Operator.greater_equal: Operator.less,
            Operator.less: Operator.greater_equal,
            Operator.less_equal: Operator.greater,
            Operator.equal_to: Operator.unequal_to,
            Operator.unequal_to: Operator.equal_to
        }[res.operator]
        return res

def new_compare(
    left: AcaciaExpr, operator: Operator,
    right: AcaciaExpr, compiler
) -> AcaciaExpr:
    # factory method
    # return an AcaciaExpr that compares `left` and `right` with `operator`
    ## the purpose is to do this optimization:
    ## when both left and right are IntLiteral
    if isinstance(left, IntLiteral) and isinstance(right, IntLiteral):
        return BoolLiteral(
            {
                Operator.greater: builtin_op.gt,
                Operator.greater_equal: builtin_op.ge,
                Operator.less: builtin_op.lt,
                Operator.less_equal: builtin_op.le,
                Operator.equal_to: builtin_op.eq,
                Operator.unequal_to: builtin_op.ne
            }[operator](left.value, right.value),
            compiler
        )
    ## fallback to BoolCompare
    return BoolCompare(left, operator, right, compiler)

class AndGroup(AcaciaExpr):
    def __init__(self, operands, compiler):
        # operands:iterable[(boolean)AcaciaExpr]
        super().__init__(compiler.types[BuiltinBoolType], compiler)
        self.main = [] # list of subcommands of /execute (See `export`)
        self.dependencies = [] # commands that runs before self.main
        # compare_operands: operands that are BoolCompare; they are converted
        # to commands when exported (there might be optimization)
        self.compare_operands = set()
        # inverted: if self is `not`ed
        self.inverted = False
        # init value
        for operand in operands:
            self._add_operand(operand)
    
    def export(self, var: BoolVar):
        # handle problem of reversing
        TRUE = 0 if self.inverted else 1
        FALSE = int(not TRUE)
        SET_FALSE = 'scoreboard players set %s %d' % (var, FALSE)
        res_dependencies = [] # dependencies part of result
        res_main = [] # main part of result (/execute subcommands)
        # -- Now convert self.compare_operands into commands --
        # Optimization: When the same expr is compared by 2 or more
        # IntLiterals, redundant ones can be removed and commands can be merged
        # e.g. `1 <= x <= 5 and x <= 3` can be merged
        # into a single /execute if score ... matches 1..3
        # 1st Pass: Throw BoolCompares that don't have an IntLiteral as operand
        # In: [a > 3, b < 5, a < 8, a > c, c > 0]
        # Out: [a > 3, b < 5, a < 8, c > 0]
        optimizable = set(filter(
            # 1. Remember that in BoolCompare.__init__, if one of left and
            # right is an IntLiteral, it must be on the right?
            # 2. != is not optimizable by `if score ... matches`
            lambda cp: (
                isinstance(cp.right, IntLiteral) and \
                cp.operator is not Operator.unequal_to
            ), self.compare_operands
        ))
        no_optimize = self.compare_operands - optimizable
        # 2nd Pass: Find BoolCompares which has an IntLiteral as operand
        # and which the other operands are the same
        # In: [a > 3, b < 5, a < 8, c > 0]
        # Out: {a: [a > 3, a < 8], b: [b < 5], c: [c > 0]}
        opt_groups = {}
        for compare in optimizable:
            group = opt_groups.get(compare.left, None)
            if group is None:
                group = []
                opt_groups[compare.left] = group
            group.append(compare)
        # 3rd Pass: Generate Commands
        for left, group in opt_groups.items():
            # Get max and min value of this group
            min_, max_ = INT_MIN, INT_MAX
            for compare in group:
                literal = compare.right.value
                if compare.operator is Operator.equal_to:
                    min_ = max(literal, min_)
                    max_ = min(literal, max_)
                # in 1st Pass Operator.unequal_to is filtered
                # so there's no need to consider it
                elif compare.operator is Operator.greater:
                    min_ = max(literal + 1, min_)
                elif compare.operator is Operator.greater_equal:
                    min_ = max(literal, min_)
                elif compare.operator is Operator.less:
                    max_ = min(literal - 1, max_)
                elif compare.operator is Operator.less_equal:
                    max_ = min(literal, max_)
            if min_ > max_: # must be False
                return [SET_FALSE]
            elif min_ == max_:
                int_range = str(min_)
            else:
                min_str = '' if min_ == INT_MIN else str(min_)
                max_str = '' if max_ == INT_MAX else str(max_)
                int_range = '%s..%s' % (min_str, max_str)
            # Calculate left (non-Literal one)
            dependency, left_var = to_IntVar(left)
            res_dependencies.extend(dependency)
            res_main.append('if score %s matches %s' % (left_var, int_range))
        # Finally, handle unoptimizable BoolCompares
        for compare in no_optimize:
            dependency, main = compare.as_execute()
            res_dependencies.extend(dependency)
            res_main.extend(main)
        # convert dependencies and main to real commands
        res_main.extend(self.main)
        res_dependencies.extend(self.dependencies)
        return res_dependencies + [
            SET_FALSE,
            export_execute_subcommands(
                res_main, 'scoreboard players set %s %d' % (var, TRUE)
            )
        ]

    def _add_operand(self, operand: AcaciaExpr):
        # add an operand to AndGroup
        if isinstance(operand, BoolVar):
            self.main.append('if score %s matches 1' % operand)
        elif isinstance(operand, NotBoolVar):
            self.main.append('if score %s matches 0' % operand)
        elif isinstance(operand, BoolCompare):
            self.compare_operands.add(operand)
        elif isinstance(operand, AndGroup):
            # combine AndGroups
            if operand.inverted:
                # `a and not (b and c)` needs a tmp var:
                # tmp = `b and c`, self = `a and not tmp`
                tmp = self.type.new_var(tmp = True)
                self.dependencies.extend(operand.export(tmp))
                self._add_operand(tmp.not_())
            else:
                self.main.extend(operand.main)
                self.dependencies.extend(operand.dependencies)
                self.compare_operands.update(operand.compare_operands)
        else:
            # BoolLiterals should have been optimized by `new_and_group`
            # AcaciaExpr which is not a boolean (which is illegal) should
            # have been detected by `new_and_group`, too
            raise ValueError
    
    def deepcopy(self):
        # return a deepcopy of self
        res = AndGroup(operands = (), compiler = self.compiler)
        res.main = deepcopy(self.main)
        res.dependencies = deepcopy(self.dependencies)
        res.inverted = self.inverted
        res.compare_operands = deepcopy(self.compare_operands)
        return res
    
    # --- UNARY OP ---
    def not_(self):
        res = self.deepcopy()
        res.inverted = not res.inverted
        return res

def new_and_group(operands: list, compiler) -> AcaciaExpr:
    # factory function of AndGroup
    ## Purpose 1. check whether operands are valid
    # make sure there is at least 1 operand
    if not operands:
        raise ValueError
    # make sure all operands are booleans
    for operand in operands:
        if not isinstance(operand.type, BuiltinBoolType):
            compiler.error(
                ErrorType.INVALID_OPERAND, operator = 'and',
                operand = repr(operand.type.name)
            )
    ## Purpose 2. to do these optimizations:
    literals = filter(
        lambda operand: isinstance(operand, BoolLiteral), operands
    )
    new_operands = list(operands) # make a deepcopy of `operands`
    for literal in literals:
        if literal.value is True:
            # throw away operands that are always true
            new_operands.remove(literal)
        else:
            # when any of the `operands` is always false, return false
            return BoolLiteral(False, compiler)
    # if there is no operands left, meaning all operands are
    # constantly true, so return true
    if not new_operands:
        return BoolLiteral(True, compiler)
    # if there is only 1 operand left, return that
    if len(new_operands) == 1:
        return new_operands[0]
    # Final fallback
    return AndGroup(operands, compiler)

def new_or_expression(operands, compiler) -> AcaciaExpr:
    # create an `or` expression
    # invert the operands (`a`, `b`, `c` -> `not a`, `not b`, `not c`)
    def _map(operand):
        if not isinstance(operand.type, BuiltinBoolType):
            compiler.error(
                ErrorType.INVALID_OPERAND, operator = 'or',
                operand = repr(operand.type.name)
            )
        return operand.not_()
    inverted_operands = list(map(_map, operands))
    # connect them with `and` (-> `not a and not b and not c`)
    res = new_and_group(
        operands = inverted_operands, compiler = compiler
    )
    # invert result (-> `not (not a and not b and not c)`)
    return res.not_()

# --- Utils ---
def to_BoolVar(expr: AcaciaExpr):
    # make any bool expr become an BoolVar,
    # with the dependencies and var apart
    # expr:(Any AcaciaExpr that are boolean type)
    # return[0]: the dependency to calculate the operand itself
    # return[1]: the final IntVar that is used
    if isinstance(expr, BoolVar):
        return (), expr
    else:
        tmp = expr.type.new_var(tmp = True)
        return expr.export(tmp), tmp
