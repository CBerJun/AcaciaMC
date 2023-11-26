"""Abstarct Syntax Tree definitions for Acacia."""
from typing import (
    Union as _Union, List as _List, Optional as _Optional, Dict as _Dict
)
import enum as _enum
import operator as _operator

####################
### AST CONTENTS ###
####################

class Operator(_enum.Enum):
    # NOTE these values are shown in error messages.
    # unary
    positive = "unary +"
    negative = "unary -"
    not_ = "not"
    # binary
    multiply = "*"
    divide = "/"
    mod = "%"
    add = "+"
    minus = "-"
    # compare
    equal_to = "=="
    unequal_to = "!="
    greater = ">"
    less = "<"
    greater_equal = ">="
    less_equal = "<="
    # boolean
    and_ = "and"
    or_ = "or"

OP2PYOP = {
    Operator.positive: _operator.pos,
    Operator.negative: _operator.neg,
    Operator.multiply: _operator.mul,
    Operator.divide: _operator.floordiv,
    Operator.mod: _operator.mod,
    Operator.add: _operator.add,
    Operator.minus: _operator.sub,
    Operator.equal_to: _operator.eq,
    Operator.unequal_to: _operator.ne,
    Operator.greater: _operator.gt,
    Operator.less: _operator.lt,
    Operator.greater_equal: _operator.ge,
    Operator.less_equal: _operator.le
}
COMPOP_INVERT = {
    # Used to invert ("not") a comparison
    Operator.greater: Operator.less_equal,
    Operator.greater_equal: Operator.less,
    Operator.less: Operator.greater_equal,
    Operator.less_equal: Operator.greater,
    Operator.equal_to: Operator.unequal_to,
    Operator.unequal_to: Operator.equal_to
}

class MethodQualifier(_enum.Enum):
    """Entity method qualifiers."""
    # These values are shown in error messages
    none = "(none)"
    virtual = "virtual"
    override = "override"

class ModuleMeta:
    """Specifies a module."""
    def __init__(self, last_name: str, leading_dots=0, parents=[]):
        self.leading_dots = leading_dots
        self.last_name = last_name
        self.parents = list(parents)

    def __str__(self) -> str:
        return ("." * self.leading_dots
                + ".".join(self.parents)
                + ("." if self.parents else "")
                + self.last_name)

#################
### AST NODES ###
#################

class AST:

    show_debug = True  # show debug info when visited

    def __init__(self, lineno: int, col: int):
        # lineno & col: position where this node starts
        self.lineno = lineno
        self.col = col

# these classes are for classifying

class Statement(AST):
    pass

class Expression(AST):
    show_debug = False

# details

class Module(AST):  # a module
    def __init__(self, body: list, lineno, col):
        super().__init__(lineno, col)
        self.body = body

class ArgumentTable(AST):  # arguments used in function definition
    show_debug = False

    def __init__(self, lineno, col):
        super().__init__(lineno, col)
        self.args: _List[str] = []  # names of arguments
        self.default = {}  # default values of arguments
        self.types = {}  # types of arguments

    def add_arg(self, name: str, type: "TypeSpec", default: Expression):
        self.args.append(name)
        self.types[name] = type
        self.default[name] = default

class CallTable(AST):  # call table
    show_debug = False

    def __init__(self, args: _List[Expression],
                 keywords: _Dict[str, Expression], lineno, col):
        super().__init__(lineno, col)
        self.args = args
        self.keywords = keywords

class TypeSpec(AST):  # specify type of value `int`
    show_debug = False

    def __init__(self, content: Expression, lineno, col):
        super().__init__(lineno, col)
        self.content = content

class FormattedStr(AST):  # a literal string with ${formatted exprs}
    show_debug = False

    def __init__(self, content: _List[_Union[Expression, str]], lineno, col):
        super().__init__(lineno, col)
        self.content = content

class ExprStatement(Statement):  # a statement that is an expression
    def __init__(self, value: AST, lineno, col):
        super().__init__(lineno, col)
        self.value = value

class Pass(Statement):  # does nothing
    pass

class If(Statement):  # if statement
    def __init__(
        self, condition: Expression,
        body: list, else_body: list, lineno, col
    ):
        super().__init__(lineno, col)
        self.condition = condition
        self.body = body
        self.else_body = else_body

class While(Statement):  # while statement
    def __init__(self, condition: Expression, body: list, lineno, col):
        super().__init__(lineno, col)
        self.condition = condition
        self.body = body

class FuncDef(Statement):
    def __init__(
        self, name: str, arg_table: ArgumentTable,
        body: list, returns: _Optional[TypeSpec], lineno, col
    ):  # function definition
        super().__init__(lineno, col)
        self.name = name
        self.arg_table = arg_table
        self.returns = returns
        self.body = body

class InlineFuncDef(Statement):
    def __init__(
        self, name: str, arg_table: ArgumentTable,
        body: list, returns: _Optional[TypeSpec], lineno, col
    ):  # inline function definition
        super().__init__(lineno, col)
        self.name = name
        self.arg_table = arg_table
        self.returns = returns
        self.body = body

class InterfaceDef(Statement):  # define an interface
    def __init__(self, path: list, body: list, lineno, col):
        super().__init__(lineno, col)
        self.path = path
        self.body = body

class EntityTemplateDef(Statement):  # entity statement
    def __init__(self, name: str, parents: list, body: list, lineno, col):
        super().__init__(lineno, col)
        self.name = name
        self.parents = parents
        self.body = body

class EntityField(Statement):  # entity field definition
    def __init__(self, name: str, type_: TypeSpec, lineno, col):
        super().__init__(lineno, col)
        self.name = name
        self.type = type_

class EntityMethod(Statement):  # entity method definition
    def __init__(self, content: _Union[FuncDef, InlineFuncDef],
                 qualifier: MethodQualifier, lineno, col):
        super().__init__(lineno, col)
        self.content = content
        self.qualifier = qualifier

class EntityMeta(Statement):  # entity meta like @type
    def __init__(self, name: str, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.name = name
        self.value = value

class VarDef(Statement):  # x: y [= z] variable declaration
    def __init__(self, target: Expression,
                 type_: TypeSpec,
                 value: _Optional[Expression],
                 lineno, col):
        super().__init__(lineno, col)
        self.target = target
        self.type = type_
        self.value = value

class AutoVarDef(Statement):  # := short variable declaration
    def __init__(self, target: Expression, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.target = target
        self.value = value

class Assign(Statement):  # normal assign
    def __init__(self, target: Expression, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.target = target
        self.value = value

class Command(Statement):  # raw command
    def __init__(self, content: FormattedStr, lineno, col):
        super().__init__(lineno, col)
        self.content = content

class AugmentedAssign(Statement):  # augmented assign
    def __init__(
        self, target: Expression, operator: Operator,
        value: Expression, lineno, col
    ):
        super().__init__(lineno, col)
        self.target = target
        self.operator = operator
        self.value = value

class Binding(Statement):  # binding
    def __init__(self, target: Expression, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.target = target
        self.value = value

class Import(Statement):  # import a module
    def __init__(self, meta: ModuleMeta, alias: _Optional[str], lineno, col):
        super().__init__(lineno, col)
        self.meta = meta
        self.name = alias
        if self.name is None:
            self.name = self.meta.last_name

class FromImport(Statement):  # import specific things from a module
    def __init__(
        self, meta: ModuleMeta, names: _List[str],
        aliases: _List[_Optional[str]], lineno, col
    ):
        super().__init__(lineno, col)
        self.meta = meta
        self.id2name = {}  # keys are actual IDs and values are aliases
        for name, alias in zip(names, aliases):
            self.id2name[name] = name if alias is None else alias

class FromImportAll(Statement):  # import everything in a module
    def __init__(self, meta: ModuleMeta, lineno, col):
        super().__init__(lineno, col)
        self.meta = meta

class For(Statement):  # for-in iteration
    def __init__(self, name: str, expr: Expression, body: list, lineno, col):
        super().__init__(lineno, col)
        self.name = name
        self.expr = expr
        self.body = body

class StructField(Statement):  # a struct's field
    def __init__(self, name: str, type_: TypeSpec, lineno, col):
        super().__init__(lineno, col)
        self.name = name
        self.type = type_

class StructDef(Statement):  # struct definition
    def __init__(self, name: str, bases: _List[Expression],
                 body: _List[_Union[StructField, Pass]], lineno, col):
        super().__init__(lineno, col)
        self.name = name
        self.bases = bases
        self.body = body

class Literal(Expression):  # a literal constant
    def __init__(self, literal, lineno, col):
        super().__init__(lineno, col)
        self.value = literal

class StrLiteral(Expression):  # a string literal
    def __init__(self, content: FormattedStr, lineno, col):
        super().__init__(lineno, col)
        self.content = content

class Self(Expression):  # "self" keyword
    pass

class Result(Expression):  # "result" keyword
    pass

class Identifier(Expression):  # an identifier
    def __init__(self, name: str, lineno, col):
        super().__init__(lineno, col)
        self.name = name

class UnaryOp(Expression):  # +x, -x, not x
    def __init__(self, operator: Operator, operand: AST, lineno, col):
        super().__init__(lineno, col)
        self.operator = operator
        self.operand = operand

class BinOp(Expression):  # an expr with binary operator (+, %, >=, etc)
    def __init__(self, left: AST, operator: Operator, right: AST, lineno, col):
        super().__init__(lineno, col)
        self.left = left
        self.operator = operator
        self.right = right

class Call(Expression):  # call a name
    def __init__(self, func: Expression, table: CallTable, lineno, col):
        super().__init__(lineno, col)
        self.func = func
        self.table = table

class Attribute(Expression):  # attr of an expr
    def __init__(self, object_: Expression, attr: str, lineno, col):
        super().__init__(lineno, col)
        self.object = object_
        self.attr = attr

class Subscript(Expression):  # value[v1, v2]
    def __init__(self, object_: Expression, subscripts: _List[Expression],
                 lineno, col):
        super().__init__(lineno, col)
        self.object = object_
        self.subscripts = subscripts

class EntityCast(Expression):  # Template@some_entity
    def __init__(self, object_: Expression, template: Expression, lineno, col):
        super().__init__(lineno, col)
        self.object = object_
        self.template = template

class CompareOp(Expression):  # ==, !=, >, <, >=, <=
    def __init__(
        self, left: Expression, operators: _List[Operator],
        operands: _List[Expression], lineno, col
    ):
        super().__init__(lineno, col)
        self.left = left
        self.operators = operators
        self.operands = operands

class BoolOp(Expression):  # and, or
    def __init__(self, operator: Operator,
                 operands: _List[Expression], lineno, col):
        super().__init__(lineno, col)
        self.operator = operator
        self.operands = operands

class RawScore(Expression):  # directly get the score on a scoreboard
    def __init__(
        self, objective: Expression, selector: Expression, lineno, col
    ):
        super().__init__(lineno, col)
        self.objective = objective
        self.selector = selector

class ListDef(Expression):  # a literal compile time list
    def __init__(self, items: _List[Expression], lineno, col):
        super().__init__(lineno, col)
        self.items = items

class MapDef(Expression):  # a map
    def __init__(self, keys: _List[Expression],
                 values: _List[Expression], lineno, col):
        super().__init__(lineno, col)
        self.keys = keys
        self.values = values

#############
### UTILS ###
#############

class ASTVisitor:
    """Base class of an AST handler."""
    def visit(self, node: AST, **kwargs):
        visitor = getattr(
            self,
            'visit_%s' % node.__class__.__name__,
            self.general_visit
        )
        return visitor(node, **kwargs)

    def general_visit(self, node: AST):
        raise NotImplementedError
