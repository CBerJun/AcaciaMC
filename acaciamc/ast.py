"""Abstarct Syntax Tree definitions for Acacia."""
from typing import (
    Union as _Union, List as _List, Tuple as _Tuple, Any as _Any
)
import enum

####################
### AST CONTENTS ###
####################

class Operator(enum.Enum):
    # unary
    positive = 0x00
    negative = 0x01
    not_ = 0x02
    # binary
    multiply = 0x10
    divide = 0x11
    mod = 0x12
    add = 0x13
    minus = 0x14
    # compare
    equal_to = 0x20
    unequal_to = 0x21
    greater = 0x22
    less = 0x23
    greater_equal = 0x24
    less_equal = 0x25
    # boolean
    and_ = 0x30
    or_ = 0x31

class ModuleMeta:
    """Specifies a module."""
    def __init__(self, last_name: str, leading_dots=0, parents=[]):
        self.leading_dots = leading_dots
        self.last_name = last_name
        self.parents = list(parents)

# This is to export `StringMode` from tokenizer
from acaciamc.tokenizer import StringMode

#################
### AST NODES ###
#################

class AST:
    def __init__(self, lineno: int, col: int):
        # lineno & col: position where this node starts
        self.lineno = lineno
        self.col = col

# these classes are for classifying
class Statement(AST): pass
class Expression(AST): pass
class AnyTypeSpec(AST): pass

# details

class Module(AST):  # a module
    def __init__(self, body: list, lineno, col):
        super().__init__(lineno, col)
        self.body = body

class ArgumentTable(AST):  # arguments used in function definition
    def __init__(self, lineno, col):
        super().__init__(lineno, col)
        self.args = []  # names of arguments
        self.default = {}  # default values of arguments
        self.types = {}  # types of arguments

    def add_arg(self, name: str, type: Expression, default: Expression):
        self.args.append(name)
        self.types[name] = type
        self.default[name] = default

class TypeSpec(AnyTypeSpec):  # specify type of value `int`
    def __init__(self, content: Expression, lineno, col):
        super().__init__(lineno, col)
        self.content = content

class EntityTypeSpec(AnyTypeSpec):  # specify entity template `entity(Temp)`
    def __init__(self, template: Expression, lineno, col):
        super().__init__(lineno, col)
        self.template = template

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
        body: list, returns: AnyTypeSpec, lineno, col
    ):  # function definition
        super().__init__(lineno, col)
        self.name = name
        self.arg_table = arg_table
        self.returns = returns
        self.body = body

class InlineFuncDef(Statement):
    def __init__(
        self, name: str, arg_table: ArgumentTable,
        body: list, returns: AnyTypeSpec, lineno, col
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
    def __init__(self, name: str, type_: AnyTypeSpec, lineno, col):
        super().__init__(lineno, col)
        self.name = name
        self.type = type_

class EntityMethod(Statement):  # entity method definition
    def __init__(self, content: _Union[FuncDef, InlineFuncDef], lineno, col):
        super().__init__(lineno, col)
        self.content = content

class EntityMeta(Statement):  # entity meta like @type
    def __init__(self, name: str, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.name = name
        self.value = value

class Assign(Statement):  # normal assign
    def __init__(self, target: Expression, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.target = target
        self.value = value

class Command(Statement):  # raw command
    def __init__(self, values: _List[_Tuple[StringMode, _Any]], lineno, col):
        super().__init__(lineno, col)
        self.values = values

class Result(Statement):  # set function result
    def __init__(self, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.value = value

class AugmentedAssign(Statement):  # augmented assign
    def __init__(
        self, target: Expression, operator: Operator,
        value: Expression, lineno, col
    ):
        super().__init__(lineno, col)
        self.target = target
        self.operator = operator
        self.value = value

class MacroBind(Statement):  # binding
    def __init__(self, target: Expression, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.target = target
        self.value = value

class Import(Statement):  # import a module
    def __init__(self, meta: ModuleMeta, alia: str, lineno, col):
        super().__init__(lineno, col)
        self.meta = meta
        self.name = alia
        if self.name is None:
            self.name = self.meta.last_name

class FromImport(Statement):  # import specific things from a module
    def __init__(
        self, meta: ModuleMeta, names: list, alias: list, lineno, col
    ):
        super().__init__(lineno, col)
        self.meta = meta
        self.id2name = {}  # keys are actual IDs and values are alias
        for name, alia in zip(names, alias):
            self.id2name[name] = name if alia is None else alia

class FromImportAll(Statement):  # import everything in a module
    def __init__(self, meta: ModuleMeta, lineno, col):
        super().__init__(lineno, col)
        self.meta = meta

class Literal(Expression):  # a literal constant
    def __init__(self, literal, lineno, col):
        super().__init__(lineno, col)
        self.value = literal

class Self(Expression):  # "self" keyword
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
    def __init__(
        self, func: Expression, args: list,
        keywords: dict, lineno, col
    ):
        super().__init__(lineno, col)
        self.func = func
        self.args = args
        self.keywords = keywords

class Attribute(Expression):  # attr of an expr
    def __init__(self, object_: Expression, attr: str, lineno, col):
        super().__init__(lineno, col)
        self.object = object_
        self.attr = attr

class EntityCast(Expression):  # Template@some_entity
    def __init__(self, object_: Expression, template: Expression, lineno, col):
        super().__init__(lineno, col)
        self.object = object_
        self.template = template

class CompareOp(Expression):  # ==, !=, >, <, >=, <=
    def __init__(
        self, left: Expression,
        operators: list, operands: list, lineno, col
    ):
        super().__init__(lineno, col)
        self.left = left
        self.operators = operators
        self.operands = operands

class BoolOp(Expression):  # and, or
    def __init__(self, operator: Operator, operands: list, lineno, col):
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
