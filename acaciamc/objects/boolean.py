"""Builtin "bool" type.

There are several classes that are used to represent bool expressions:
- BoolLiteral: boolean literal (True or False).
- BoolVar: boolean variable. We use a score to store a boolean.
  When a score == 1, it's True; when score == 0, it's False.
- NotBoolVar: inverted (`not var`) form of `BoolVar`.
- CompareBase: abstract class that should be returned by
  `AcaciaExpr.compare` to implement comparison operators. 
- WildBool: stores any boolean expression. It consists of two parts:
  the command dependencies and /execute subcommands. The expression
  is True if and only if the subcommands executed successfully.
  It also stores "ranges" of a specific scoreboard slot (this is used
  as an optimization for "and" expressions).
- NotWildBool: inverted (`not expr`) form of `WildBool`.

Q: WHERE ARE `and` AND `or` EXPRESSION STORED???
A: `and` expressions are created using `new_and_group`. Normally a
`WildBool` is returned but some optimizations may apply. `or`
expressions are all converted into other types of expressions. This
is done by `new_or_expression`.
"""

__all__ = [
    # Type
    'BoolType', 'BoolDataType',
    # Expressions
    'BoolLiteral', 'BoolVar', 'NotBoolVar', 'CompareBase', 'WildBool',
    'NotWildBool', 'SupportsAsExecute',
    # Factory functions
    'new_and_group', 'new_or_expression',
    # Utils
    'to_BoolVar'
]

from abc import ABCMeta, abstractmethod
from typing import List, Tuple, Dict, Optional, TYPE_CHECKING

import acaciamc.mccmdgen.cmds as cmds
from acaciamc.ast import Operator, COMPOP_INVERT
from acaciamc.constants import INT_MAX, INT_MIN
from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import (
    DefaultDataType, Storable, SupportsEntityField
)
from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.utils import InvalidOpError
from .types import Type

if TYPE_CHECKING:
    from acaciamc.mccmdgen.cmds import _ExecuteSubcmd
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.ctexpr import CTObj


def _bool_compare(self: AcaciaExpr, op: Operator, other: AcaciaExpr, compiler):
    """Wildcard `compare` method to compare a bool with a bool."""
    if not (op is Operator.equal_to or op is Operator.unequal_to):
        raise InvalidOpError
    dep = []
    invert = op is Operator.unequal_to
    if isinstance(other, BoolVar):
        slot2 = other.slot
    elif isinstance(other, NotBoolVar):
        slot2 = other.slot
        invert = not invert
    elif isinstance(other, (CompareBase, WildBool)):
        _dep, other_var = to_BoolVar(other, compiler)
        dep.extend(_dep)
        slot2 = other_var.slot
    else:
        raise InvalidOpError
    _dep, self_var = to_BoolVar(self, compiler)
    dep.extend(_dep)
    return ScbEqualCompare(self_var.slot, slot2, invert, dep)


def _export_bool(subcmds: List["_ExecuteSubcmd"], var: "BoolVar",
                 compiler: "Compiler", invert=False) -> CMDLIST_T:
    res = []
    FALSE = int(invert)
    TRUE = 1 - FALSE
    # decide if temporary value is needed
    need_tmp = False
    for subcmd in subcmds:
        if subcmd.scb_did_read(var.slot):
            need_tmp = True
            break
    if need_tmp:
        tmp = compiler.allocate_tmp()
    else:
        tmp = var.slot
    # set target to False first
    res.append(cmds.ScbSetConst(tmp, FALSE))
    # check condition and change it to True
    res.append(cmds.Execute(subcmds, cmds.ScbSetConst(tmp, TRUE)))
    if need_tmp:
        res.append(cmds.ScbOperation(cmds.ScbOp.ASSIGN, var.slot, tmp))
    return res


def _bool_rawtextify(self: AcaciaExpr, compiler: "Compiler"):
    """A generic `rawtextify` implementation for bool."""
    dependencies, var = to_BoolVar(self, compiler)
    return [cmds.RawtextScore(var.slot)], dependencies


class BoolDataType(DefaultDataType, Storable, SupportsEntityField):
    name = "bool"

    def new_var(self, compiler) -> "BoolVar":
        return BoolVar.new(compiler)

    def new_entity_field(self, compiler):
        return {"scoreboard": compiler.add_scoreboard()}

    def new_var_as_field(self, entity, scoreboard: str) -> "BoolVar":
        return BoolVar(cmds.ScbSlot(entity.to_str(), scoreboard))


ctdt_bool = CTDataType("bool")


class BoolType(Type):
    def datatype_hook(self):
        return BoolDataType()

    def cdatatype_hook(self):
        return ctdt_bool


class SupportsAsExecute(AcaciaExpr, metaclass=ABCMeta):
    """See `as_execute` method. Should only be used by booleans."""

    @abstractmethod
    def as_execute(self, compiler) -> Tuple[CMDLIST_T, List["_ExecuteSubcmd"]]:
        """
        Convert this expression to some dependency commands and
        subcommands of /execute. Value of this expression is considered
        True if and only if the subcommands executed successfully.
        """
        pass


class BoolLiteral(ConstExprCombined):
    """Literal boolean."""
    cdata_type = ctdt_bool

    def __init__(self, value: bool):
        super().__init__(BoolDataType())
        self.value = value

    def export(self, var: "BoolVar", compiler):
        return [cmds.ScbSetConst(var.slot, int(self.value))]

    def cstringify(self) -> str:
        return "true" if self.value else "false"

    def rawtextify(self, compiler):
        return [cmds.RawtextText("1" if self.value else "0")], []

    def chash(self):
        return self.value

    def compare(self, op: Operator, other: AcaciaExpr, compiler):
        if not (op is Operator.equal_to or op is Operator.unequal_to):
            raise InvalidOpError
        # For a boolean expression b, b == True is equivalent to "b"
        # b == False is equivalent to "not b"; != is the opposite
        true = self.value == (op is Operator.equal_to)
        if self.data_type.is_type_of(other):
            return other if true else other.unarynot(compiler)

    def ccompare(self, op: Operator, other: "CTObj"):
        if not (op is Operator.equal_to or op is Operator.unequal_to):
            raise InvalidOpError
        true = self.value == (op is Operator.equal_to)
        if isinstance(other, BoolLiteral):
            return other.value == true
        raise InvalidOpError

    def __str__(self):
        """Return 1 if True, 0 if False."""
        return str(int(self.value))

    # Unary operator
    def cunarynot(self):
        return BoolLiteral(not self.value)


class BoolVar(VarValue, SupportsAsExecute):
    """Boolean stored as a score on scoreboard."""

    def __init__(self, slot: cmds.ScbSlot):
        super().__init__(BoolDataType())
        self.slot = slot

    @classmethod
    def new(cls, compiler: "Compiler", tmp=False):
        alloc = compiler.allocate_tmp if tmp else compiler.allocate
        return cls(alloc())

    def as_execute(self, compiler):
        return [], [cmds.ExecuteScoreMatch(self.slot, '1')]

    def __str__(self):
        return self.slot.to_str()

    def export(self, var: "BoolVar", compiler):
        return [cmds.ScbOperation(cmds.ScbOp.ASSIGN, var.slot, self.slot)]

    def compare(self, op, other, compiler):
        if not (op is Operator.equal_to or op is Operator.unequal_to):
            raise InvalidOpError
        if not isinstance(other, BoolVar):
            raise InvalidOpError
        invert = op is Operator.unequal_to
        return ScbEqualCompare(self.slot, other.slot, invert)

    def swap(self, other: "BoolVar", compiler):
        return [cmds.ScbOperation(cmds.ScbOp.SWAP, self.slot, other.slot)]

    rawtextify = _bool_rawtextify

    # Unary operator
    def unarynot(self, compiler):
        return NotBoolVar(self.slot)


class NotBoolVar(AcaciaExpr):
    def __init__(self, slot: cmds.ScbSlot):
        super().__init__(BoolDataType())
        self.slot = slot

    def __str__(self):
        return self.slot.to_str()

    def as_execute(self, compiler):
        return [], [cmds.ExecuteScoreMatch(self.slot, '0')]

    def export(self, var: BoolVar, compiler):
        if var.slot == self.slot:
            # negation of self
            return [
                cmds.ScbAddConst(var.slot, 1),
                cmds.Execute([cmds.ExecuteScoreMatch(var.slot, "2")],
                             cmds.ScbSetConst(var.slot, 0))
            ]
        else:
            return [
                cmds.ScbSetConst(var.slot, 0),
                cmds.Execute([cmds.ExecuteScoreMatch(self.slot, "0")],
                             cmds.ScbSetConst(var.slot, 1))
            ]

    def compare(self, op, other, compiler):
        if not (op is Operator.equal_to or op is Operator.unequal_to):
            raise InvalidOpError
        if not isinstance(other, (BoolVar, NotBoolVar)):
            raise InvalidOpError
        invert = (op is Operator.equal_to) == (isinstance(other, BoolVar))
        return ScbEqualCompare(self.slot, other.slot, invert)

    rawtextify = _bool_rawtextify

    # Unary operator
    def unarynot(self, compiler):
        res = BoolVar(self.slot)
        res.is_temporary = True
        return res


class CompareBase(SupportsAsExecute, metaclass=ABCMeta):
    def __init__(self):
        super().__init__(BoolDataType())

    def export(self, var: BoolVar, compiler):
        res, subcmds = self.as_execute(compiler)
        res.extend(_export_bool(subcmds, var, compiler))
        return res

    compare = _bool_compare
    rawtextify = _bool_rawtextify

    @abstractmethod
    def unarynot(self, compiler):
        # Boolean expressions should implement "not".
        pass


class ScbMatchesCompare(CompareBase):
    def __init__(
            self, dependencies: CMDLIST_T, slot: cmds.ScbSlot,
            operator: Operator, literal: int
    ):
        super().__init__()
        self.dependencies = dependencies
        self.slot = slot
        self.operator = operator
        self.literal = literal

    def as_execute(self, compiler) -> Tuple[CMDLIST_T, List["_ExecuteSubcmd"]]:
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
    def unarynot(self, compiler):
        return ScbMatchesCompare(
            self.dependencies.copy(), self.slot, COMPOP_INVERT[self.operator],
            self.literal
        )


class ScbEqualCompare(CompareBase):
    def __init__(self, left: cmds.ScbSlot, right: cmds.ScbSlot,
                 invert=False, dependencies: Optional[CMDLIST_T] = None):
        super().__init__()
        self.left = left
        self.right = right
        self.invert = invert
        if dependencies is None:
            self.dependencies = []
        else:
            self.dependencies = dependencies

    def as_execute(self, compiler) -> Tuple[CMDLIST_T, List["_ExecuteSubcmd"]]:
        return (
            self.dependencies.copy(),
            [cmds.ExecuteScoreComp(
                self.left, self.right, cmds.ScbCompareOp.EQ, self.invert
            )]
        )

    def unarynot(self, compiler):
        return ScbEqualCompare(
            self.left, self.right, not self.invert,
            self.dependencies
        )


MCRange = Tuple[cmds.ScbSlot, int, int]


def _ranges2subcmds(ranges: List[MCRange]) -> List["_ExecuteSubcmd"]:
    res = []
    for slot, min_, max_ in ranges:
        if min_ == INT_MIN and max_ == INT_MAX:
            continue
        if min_ == max_:
            int_range = str(min_)
        else:
            min_str = '' if min_ == INT_MIN else str(min_)
            max_str = '' if max_ == INT_MAX else str(max_)
            int_range = '%s..%s' % (min_str, max_str)
        res.append(cmds.ExecuteScoreMatch(slot, int_range))
    return res


class WildBool(SupportsAsExecute):
    def __init__(
            self, subcmds: List["_ExecuteSubcmd"],
            dependencies: CMDLIST_T,
            ranges: Optional[List[MCRange]] = None
    ):
        super().__init__(BoolDataType())
        self.subcmds = subcmds
        self.dependencies = dependencies
        if ranges is None:
            ranges = []
        self.ranges = ranges

    def export(self, var: BoolVar, compiler):
        res, subcmds = self.as_execute(compiler)
        res.extend(_export_bool(subcmds, var, compiler))
        return res

    def as_execute(self, compiler):
        subcmds = self.subcmds + _ranges2subcmds(self.ranges)
        return self.dependencies.copy(), subcmds

    compare = _bool_compare
    rawtextify = _bool_rawtextify

    # Unary operator
    def unarynot(self, compiler):
        return NotWildBool(
            self.subcmds.copy(), self.dependencies.copy(),
            self.ranges.copy()
        )


class NotWildBool(AcaciaExpr):
    def __init__(
            self, subcmds: List["_ExecuteSubcmd"],
            dependencies: CMDLIST_T,
            ranges: Optional[List[MCRange]] = None
    ):
        super().__init__(BoolDataType())
        self.subcmds = subcmds
        self.dependencies = dependencies
        if ranges is None:
            ranges = []
        self.ranges = ranges

    def export(self, var: BoolVar, compiler):
        subcmds = self.subcmds + _ranges2subcmds(self.ranges)
        res = self.dependencies.copy()
        res.extend(_export_bool(subcmds, var, compiler, invert=True))
        return res

    compare = _bool_compare
    rawtextify = _bool_rawtextify

    # Unary operator
    def unarynot(self, compiler):
        return WildBool(
            self.subcmds.copy(), self.dependencies.copy(),
            self.ranges.copy()
        )


def new_and_group(operands: List[AcaciaExpr], compiler) -> AcaciaExpr:
    """Creates an "and" expression."""
    assert operands
    literals = [operand for operand in operands
                if isinstance(operand, BoolLiteral)]
    new_operands = operands.copy()
    for literal in literals:
        if literal.value:
            # throw away operands that are always true
            new_operands.remove(literal)
        else:
            # when any operand is literal false, the result is false
            return BoolLiteral(False)
    # if there is no operand left, return true
    if not new_operands:
        return BoolLiteral(True)
    # if there is only 1 operand left, return that
    if len(new_operands) == 1:
        return new_operands[0]
    # fallback
    res_subcmds: List[_ExecuteSubcmd] = []
    res_commands: CMDLIST_T = []
    ranges: Dict[cmds.ScbSlot, List[int]] = {}
    for operand in new_operands:
        if isinstance(operand, WildBool):
            res_subcmds.extend(operand.subcmds)
            res_commands.extend(operand.dependencies)
            for slot, min_, max_ in operand.ranges:
                rng = ranges.setdefault(slot, [INT_MIN, INT_MAX])
                rng[0] = max(min_, rng[0])
                rng[1] = min(max_, rng[1])
            operand = None
        elif isinstance(operand, NotWildBool):
            # `a and not (b and c)` needs a tmp var:
            # tmp = `not (b and c)`, self = `a and tmp`
            tmp = BoolVar.new(tmp=True, compiler=compiler)
            res_commands.extend(operand.export(tmp, compiler))
            operand = tmp
        elif (isinstance(operand, ScbMatchesCompare)
              and operand.operator is not Operator.unequal_to):
            # Optimization: When the same expr is compared to two or more
            # `IntLiteral`s, execute score matches subcommands can be merged.
            # e.g. `1 <= x <= 5 and x <= 3` can be merged into a single
            # /execute if score ... matches 1..3
            rng = ranges.setdefault(operand.slot, [INT_MIN, INT_MAX])
            res_commands.extend(operand.dependencies)
            literal = operand.literal
            if operand.operator is Operator.equal_to:
                rng[0] = max(literal, rng[0])
                rng[1] = min(literal, rng[1])
            elif operand.operator is Operator.greater:
                rng[0] = max(literal + 1, rng[0])
            elif operand.operator is Operator.greater_equal:
                rng[0] = max(literal, rng[0])
            elif operand.operator is Operator.less:
                rng[1] = min(literal - 1, rng[1])
            elif operand.operator is Operator.less_equal:
                rng[1] = min(literal, rng[1])
            if rng[0] > rng[1]:  # must be False
                return BoolLiteral(False)
            operand = None
        if operand is not None:
            assert isinstance(operand, (BoolVar, NotBoolVar, CompareBase))
            commands, subcmds = operand.as_execute(compiler)
            res_commands.extend(commands)
            res_subcmds.extend(subcmds)
    res_ranges = [(slot, *rng) for slot, rng in ranges.items()
                  if rng[0] != INT_MIN or rng[1] != INT_MAX]
    # if there is no subcommands generated, then just return True since
    # no restrictions is added.
    if not res_subcmds and not res_ranges:
        return BoolLiteral(True)
    # Final fallback
    return WildBool(res_subcmds, res_commands, res_ranges)


def new_or_expression(operands: List[AcaciaExpr], compiler) -> AcaciaExpr:
    """Create an "or" expression."""
    # invert the operands (`a`, `b`, `c` -> `not a`, `not b`, `not c`)
    inverted_operands = [operand.unarynot(compiler) for operand in operands]
    # connect them with `and` (-> `not a and not b and not c`)
    res = new_and_group(operands=inverted_operands, compiler=compiler)
    # invert result (-> `not (not a and not b and not c)`)
    return res.unarynot(compiler)


# Utils
def to_BoolVar(expr: AcaciaExpr, compiler, tmp=True) \
        -> Tuple[CMDLIST_T, BoolVar]:
    """Convert any boolean expression to a `BoolVar` and some commands.
    return[0]: the commands to run
    return[1]: the `BoolVar`
    """
    if isinstance(expr, BoolVar):
        return [], expr
    else:
        var = BoolVar.new(compiler, tmp=tmp)
        return expr.export(var, compiler), var
