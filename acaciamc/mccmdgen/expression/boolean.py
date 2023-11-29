"""Builtin "bool" type.

There are several classes that are used to represent bool expressions:
- BoolLiteral: boolean literal (True or False).
- BoolVar: boolean variable. We use a score to store a boolean.
  When a score == 1, it's True; when score == 0, it's False.
- NotBoolVar: inverted (`not var`) form of `BoolVar`.
- CompareBase: abstract class that should be returned by
  `AcaciaExpr.compare` to implement comparison operators. 
- AndGroup: store several bool expressions that are connected with
  "and". Always use factory `new_and_group`.

Q: WHERE IS AN `or` EXPRESSION STORED???
A: `or` expressions are all converted into other types of expressions
this is done by `new_or_expression`.
"""

__all__ = [
    # Type
    'BoolType', 'BoolDataType',
    # Expressions
    'BoolLiteral', 'BoolVar', 'NotBoolVar', 'CompareBase', 'AndGroup',
    # Factory functions
    'new_and_group', 'new_or_expression',
    # Utils
    'to_BoolVar'
]

from typing import Iterable, List, Tuple, Set, Dict, Optional, TYPE_CHECKING
from abc import ABCMeta, abstractmethod

from .base import *
from .types import Type
from acaciamc.ast import Operator, COMPOP_INVERT
from acaciamc.error import *
from acaciamc.constants import INT_MAX, INT_MIN
from acaciamc.mccmdgen.datatype import (
    DefaultDataType, Storable, SupportsEntityField
)
import acaciamc.mccmdgen.cmds as cmds

if TYPE_CHECKING:
    from acaciamc.mccmdgen.cmds import _ExecuteSubcmd
    from acaciamc.compiler import Compiler

export_need_tmp_bool = export_need_tmp(
    new_tmp=lambda c: BoolVar.new(c, tmp=True)
)

def _bool_compare(self: AcaciaExpr, op: Operator, other: AcaciaExpr):
    """Wildcard `compare` method to compare a bool with a bool."""
    if not (op is Operator.equal_to or op is Operator.unequal_to):
        return NotImplemented
    dep = []
    invert = op is Operator.unequal_to
    if isinstance(other, BoolVar):
        slot2 = other.slot
    elif isinstance(other, NotBoolVar):
        slot2 = other.slot
        invert = not invert
    elif isinstance(other, (CompareBase, AndGroup)):
        _dep, other_var = to_BoolVar(other)
        dep.extend(_dep)
        slot2 = other_var.slot
    else:
        return NotImplemented
    _dep, self_var = to_BoolVar(self)
    dep.extend(_dep)
    return ScbEqualCompare(
        self_var.slot, slot2, self.compiler, invert, dep
    )

class BoolDataType(DefaultDataType, Storable, SupportsEntityField):
    name = "bool"

    def new_var(self) -> "BoolVar":
        return BoolVar.new(self.compiler)

    def new_entity_field(self):
        return {"scoreboard": self.compiler.add_scoreboard()}

    def new_var_as_field(self, entity, **meta) -> "BoolVar":
        return BoolVar(cmds.ScbSlot(entity.to_str(), meta["scoreboard"]),
                       self.compiler)

class BoolType(Type):
    def datatype_hook(self):
        return BoolDataType(self.compiler)

class BoolLiteral(AcaciaExpr):
    """Literal boolean."""
    def __init__(self, value: bool, compiler):
        super().__init__(BoolDataType(compiler), compiler)
        self.value = value

    def export(self, var: "BoolVar"):
        return [cmds.ScbSetConst(var.slot, int(self.value))]

    def cmdstr(self) -> str:
        return "true" if self.value else "false"

    def map_hash(self):
        return self.value

    def copy(self) -> "BoolLiteral":
        return BoolLiteral(value=self.value, compiler=self.compiler)

    def compare(self, op, other):
        if not (op is Operator.equal_to or op is Operator.unequal_to):
            return NotImplemented
        # For a boolean expression b, b == True is equivalent to "b"
        # b == False is equivalent to "not b"; != is the opposite
        if self.value == (op is Operator.equal_to):
            return other
        else:
            return other.not_()

    def __str__(self):
        """Return 1 if True, 0 if False."""
        return str(int(self.value))

    # Unary operator
    def not_(self):
        res = self.copy()
        res.value = not res.value
        return res

class BoolVar(VarValue):
    """Boolean stored as a score on scoreboard."""
    def __init__(self, slot: cmds.ScbSlot, compiler):
        super().__init__(BoolDataType(compiler), compiler)
        self.slot = slot

    @classmethod
    def new(cls, compiler: "Compiler", tmp=False):
        alloc = compiler.allocate_tmp if tmp else compiler.allocate
        return cls(alloc(), compiler)

    def __str__(self):
        return self.slot.to_str()

    def export(self, var: "BoolVar"):
        return [cmds.ScbOperation(cmds.ScbOp.ASSIGN, var.slot, self.slot)]

    def compare(self, op, other):
        if not (op is Operator.equal_to or op is Operator.unequal_to):
            return NotImplemented
        if not isinstance(other, BoolVar):
            return NotImplemented
        invert = op is Operator.unequal_to
        return ScbEqualCompare(self.slot, other.slot, self.compiler, invert)

    # Unary operator
    def not_(self):
        return NotBoolVar(self.slot, self.compiler)

class NotBoolVar(AcaciaExpr):
    def __init__(self, slot: cmds.ScbSlot, compiler):
        super().__init__(BoolDataType(compiler), compiler)
        self.slot = slot

    def __str__(self):
        return self.slot.to_str()

    @export_need_tmp_bool
    def export(self, var: BoolVar):
        return [
            cmds.ScbSetConst(var.slot, 0),
            cmds.Execute([cmds.ExecuteScoreMatch(self.slot, "0")],
                         cmds.ScbSetConst(var.slot, 1))
        ]

    def compare(self, op, other):
        if not (op is Operator.equal_to or op is Operator.unequal_to):
            return NotImplemented
        if not isinstance(other, (BoolVar, NotBoolVar)):
            return NotImplemented
        invert = (op is Operator.equal_to) == (isinstance(other, BoolVar))
        return ScbEqualCompare(self.slot, other.slot, self.compiler, invert)

    # Unary operator
    def not_(self):
        return BoolVar(self.slot, self.compiler)

class CompareBase(AcaciaExpr, metaclass=ABCMeta):
    def __init__(self, compiler: "Compiler"):
        super().__init__(BoolDataType(compiler), compiler)

    @abstractmethod
    def as_execute(self) -> Tuple[CMDLIST_T, List["_ExecuteSubcmd"]]:
        """
        Convert this compare to some dependency commands and subcommands
        of /execute. The compare will be True if the subcommands
        executed successfully.
        """
        pass

    @export_need_tmp_bool
    def export(self, var: BoolVar):
        # set `res` to dependencies that as_execute returns
        res, subcmds = self.as_execute()
        # set target to 0 (False) first
        res.append(cmds.ScbSetConst(var.slot, 0))
        # check condition and change it to 1 (True)
        res.append(cmds.Execute(subcmds, cmds.ScbSetConst(var.slot, 1)))
        return res

    compare = _bool_compare

    @abstractmethod
    def not_(self):
        # Boolean expressions should implement "not".
        pass

class ScbMatchesCompare(CompareBase):
    def __init__(
        self, dependencies: CMDLIST_T, slot: cmds.ScbSlot,
        operator: Operator, literal: int, compiler
    ):
        super().__init__(compiler)
        self.dependencies = dependencies
        self.slot = slot
        self.operator = operator
        self.literal = literal

    def as_execute(self) -> Tuple[CMDLIST_T, List["_ExecuteSubcmd"]]:
        res = []
        match_range = {
            Operator.greater: '%d..' % (self.literal + 1),
            Operator.greater_equal: '%d..' % self.literal,
            Operator.less: '..%d' % (self.literal - 1),
            Operator.less_equal: '..%d' % self.literal,
            Operator.equal_to: str(self.literal),
            Operator.unequal_to: '!%d' % self.literal
        }[self.operator]
        res.append(cmds.ExecuteScoreMatch(self.slot, match_range))
        return self.dependencies.copy(), res

    # Unary operator
    def not_(self):
        return ScbMatchesCompare(
            self.dependencies.copy(), self.slot, COMPOP_INVERT[self.operator],
            self.literal, self.compiler
        )

class ScbEqualCompare(CompareBase):
    def __init__(self, left: cmds.ScbSlot, right: cmds.ScbSlot,
                 compiler, invert=False,
                 dependencies: Optional[CMDLIST_T] = None):
        super().__init__(compiler)
        self.left = left
        self.right = right
        self.invert = invert
        if dependencies is None:
            self.dependencies = []
        else:
            self.dependencies = dependencies

    def as_execute(self) -> Tuple[CMDLIST_T, List["_ExecuteSubcmd"]]:
        return (
            self.dependencies.copy(),
            [cmds.ExecuteScoreComp(
                self.left, self.right, cmds.ScbCompareOp.EQ, self.invert
            )]
        )

    def not_(self):
        return ScbEqualCompare(
            self.left, self.right, self.compiler, not self.invert
        )

class AndGroup(AcaciaExpr):
    def __init__(self, operands: Iterable[AcaciaExpr], compiler):
        super().__init__(BoolDataType(compiler), compiler)
        self.main: List["_ExecuteSubcmd"] = []
        self.dependencies: CMDLIST_T = []  # commands before `self.main`
        # `optimizable_operands` are converted to commands when
        # `export`ed since there may be optimizations.
        self.optimizable_operands: Set[ScbMatchesCompare] = set()
        self.inverted = False  # if this is "not"ed
        for operand in operands:
            self._add_operand(operand)

    @export_need_tmp_bool
    def export(self, var: BoolVar):
        # Handle inversion
        TRUE = 0 if self.inverted else 1
        FALSE = int(not TRUE)
        SET_FALSE = cmds.ScbSetConst(var.slot, FALSE)
        res_dependencies = []  # dependencies part of result
        res_main = []  # main part of result (/execute subcommands)
        # -- Now convert self.optimizable_operands into commands --
        # Optimization: When the same expr is compared by 2 or more
        # IntLiterals, redundant ones can be removed and commands can be merged
        # e.g. `1 <= x <= 5 and x <= 3` can be merged
        # into a single /execute if score ... matches 1..3
        # 1st Pass: Find IntCompares which has an IntLiteral as operand
        # and which the other operands are the same
        # In: [a > 3, b < 5, a < 8, c > 0]
        # Out: {a: [a > 3, a < 8], b: [b < 5], c: [c > 0]}
        opt_groups: Dict[cmds.ScbSlot, List[ScbMatchesCompare]] = {}
        for compare in self.optimizable_operands:
            group = opt_groups.get(compare.slot, None)
            if group is None:
                group = []
                opt_groups[compare.slot] = group
            group.append(compare)
        # 2nd Pass: Generate Commands
        for slot, group in opt_groups.items():
            # Get max and min value of this group
            min_, max_ = INT_MIN, INT_MAX
            dependencies = []
            for compare in group:
                dependencies.extend(compare.dependencies)
                literal = compare.literal
                if compare.operator is Operator.equal_to:
                    min_ = max(literal, min_)
                    max_ = min(literal, max_)
                # Operator.unequal_to is filtered in `_add_operand`
                # because it can't be optimized.
                elif compare.operator is Operator.greater:
                    min_ = max(literal + 1, min_)
                elif compare.operator is Operator.greater_equal:
                    min_ = max(literal, min_)
                elif compare.operator is Operator.less:
                    max_ = min(literal - 1, max_)
                elif compare.operator is Operator.less_equal:
                    max_ = min(literal, max_)
            if min_ > max_:  # must be False
                return [SET_FALSE]
            elif min_ == max_:
                int_range = str(min_)
            else:
                min_str = '' if min_ == INT_MIN else str(min_)
                max_str = '' if max_ == INT_MAX else str(max_)
                int_range = '%s..%s' % (min_str, max_str)
            # Calculate left (non-Literal one)
            res_dependencies.extend(dependencies)
            res_main.append(cmds.ExecuteScoreMatch(slot, int_range))
        # Convert dependencies and `res_main` to real commands
        res_main.extend(self.main)
        res_dependencies.extend(self.dependencies)
        return res_dependencies + [
            SET_FALSE,
            cmds.Execute(res_main, cmds.ScbSetConst(var.slot, TRUE))
        ]

    def _add_operand(self, operand: AcaciaExpr):
        """Add an operand to this `AndGroup`."""
        if isinstance(operand, BoolVar):
            self.main.append(cmds.ExecuteScoreMatch(operand.slot, '1'))
        elif isinstance(operand, NotBoolVar):
            self.main.append(cmds.ExecuteScoreMatch(operand.slot, '0'))
        elif (isinstance(operand, ScbMatchesCompare)
                and operand.operator is not Operator.unequal_to):
            self.optimizable_operands.add(operand)
        elif isinstance(operand, CompareBase):
            commands, subcmds = operand.as_execute()
            self.dependencies.extend(commands)
            self.main.extend(subcmds)
        elif isinstance(operand, AndGroup):
            # Combine AndGroups
            if operand.inverted:
                # `a and not (b and c)` needs a tmp var:
                # tmp = `not (b and c)`, self = `a and tmp`
                tmp = BoolVar.new(tmp=True, compiler=self.compiler)
                self.dependencies.extend(operand.export(tmp))
                self._add_operand(tmp)
            else:
                self.main.extend(operand.main)
                self.dependencies.extend(operand.dependencies)
                self.optimizable_operands.update(operand.optimizable_operands)
        else:
            # `BoolLiteral`s should have been optimized by
            # `new_and_group`. `AcaciaExpr`s which are not boolean type
            # (which is illegal) should have been detected by that too.
            raise ValueError

    def copy(self):
        res = AndGroup(operands=(), compiler=self.compiler)
        res.main.extend(self.main)
        res.dependencies.extend(self.dependencies)
        res.inverted = self.inverted
        res.optimizable_operands.update(self.optimizable_operands)
        return res

    compare = _bool_compare

    # Unary operator
    def not_(self):
        res = self.copy()
        res.inverted = not res.inverted
        return res

def new_and_group(operands: List[AcaciaExpr], compiler) -> AcaciaExpr:
    """Creates a boolean value connected with "and"."""
    assert operands
    # The purpose is to do these optimizations:
    literals = [operand for operand in operands
                if isinstance(operand, BoolLiteral)]
    new_operands = operands.copy()
    for literal in literals:
        if literal.value:
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
    return AndGroup(new_operands, compiler)

def new_or_expression(operands: List[AcaciaExpr], compiler) -> AcaciaExpr:
    """Create a boolean value connected with "or"."""
    # invert the operands (`a`, `b`, `c` -> `not a`, `not b`, `not c`)
    inverted_operands = [operand.not_() for operand in operands]
    # connect them with `and` (-> `not a and not b and not c`)
    res = new_and_group(operands=inverted_operands, compiler=compiler)
    # invert result (-> `not (not a and not b and not c)`)
    return res.not_()

# Utils
def to_BoolVar(expr: AcaciaExpr, tmp=True) -> Tuple[CMDLIST_T, BoolVar]:
    """Convert any boolean expression to a `BoolVar` and some commands.
    return[0]: the commands to run
    return[1]: the `BoolVar`
    """
    if isinstance(expr, BoolVar):
        return [], expr
    else:
        var = BoolVar.new(expr.compiler, tmp=tmp)
        return expr.export(var), var
