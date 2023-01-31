# Abstarct Syntax Tree definitions for Acacia
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

# This is to export StringMode from tokenizer
from .tokenizer import StringMode

#################
### AST NODES ###
#################

class AST:
    def __init__(self, lineno, col):
        # lineno & col:int place where AST starts
        self.lineno = lineno
        self.col = col
        
# these classes are for classifying
class Statement(AST): pass
class Expression(AST): pass

# details

class Module(AST): # a module
    def __init__(self, body: list, lineno, col):
        super().__init__(lineno, col)
        self.body = body
        
class ArgumentTable(AST): # arguments used in function definition
    def __init__(self, lineno, col):
        super().__init__(lineno, col)
        self.args = [] # names of arguments
        self.default = {} # default values of arguments
        self.types = {} # types of arguments
            
    def add_arg(self, name: str, type: Expression, default: Expression):
        self.args.append(name)
        self.types[name] = type
        self.default[name] = default

class ExprStatement(Statement): # a statement that is an expression
    def __init__(self, value: AST, lineno, col):
        super().__init__(lineno, col)
        self.value = value
        
class Pass(Statement): pass # does nothing

class If(Statement): # if statement
    def __init__(
        self, condition: Expression, 
        body: list, else_body: list, lineno, col
    ):
        super().__init__(lineno, col)
        self.condition = condition
        self.body = body
        self.else_body = else_body
        
class FuncDef(Statement):
    def __init__(
        self, name: str, arg_table: ArgumentTable,
        body: list, returns: Expression, lineno, col
    ):
        super().__init__(lineno, col)
        self.name = name
        self.arg_table = arg_table
        self.returns = returns
        self.body = body

class InterfaceDef(Statement):
    def __init__(self, name: str, body: list, lineno, col):
        super().__init__(lineno, col)
        self.name = name
        self.body = body
        
class Assign(Statement): # normal assign
    def __init__(self, target: Expression, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.target = target
        self.value = value
        
class Command(Statement): # raw command
    def __init__(self, values: list, lineno, col):
        # values:list[tuple(StringMode, any)]
        super().__init__(lineno, col)
        self.values = values
        
class Result(Statement): # set func result
    def __init__(self, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.value = value

class AugmentedAssign(Statement): # augmented assign
    def __init__(
        self, target: Expression, operator: Operator,
        value: Expression, lineno, col
    ):
        super().__init__(lineno, col)
        self.target = target
        self.operator = operator
        self.value = value
        
class MacroBind(Statement): # define a macro
    def __init__(self, target: Expression, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.target = target
        self.value = value
        
class Import(Statement): # import a module
    def __init__(
        self, leading_dots: int, last_name: str, parents: list, lineno, col
    ):
        super().__init__(lineno, col)
        self.leadint_dots = leading_dots
        self.last_name = last_name
        self.parents = parents
        
class Literal(Expression): # a literal constant
    def __init__(self, literal, lineno, col):
        super().__init__(lineno, col)
        self.value = literal
        
class Identifier(Expression): # an identifier
    def __init__(self, name: str, lineno, col):
        super().__init__(lineno, col)
        self.name = name
        
class UnaryOp(Expression): # +x, -x, not x
    def __init__(self, operator: Operator, operand: AST, lineno, col):
        super().__init__(lineno, col)
        self.operator = operator
        self.operand = operand
        
class BinOp(Expression): # an expr with binary operator (+, %, >=, etc)
    def __init__(self, left: AST, operator: Operator, right: AST, lineno, col):
        super().__init__(lineno, col)
        self.left = left
        self.operator = operator
        self.right = right
        
class Call(Expression): # call a name
    def __init__(
        self, func: Expression, args: list,
        keywords: dict, lineno, col
    ):
        super().__init__(lineno, col)
        self.func = func
        self.args = args
        self.keywords = keywords
        
class Attribute(Expression): # attr of an expr
    def __init__(self, object_: Expression, attr: str, lineno, col):
        super().__init__(lineno, col)
        self.object = object_
        self.attr = attr
        
class CompareOp(Expression): # ==, !=, >, <, >=, <=
    def __init__(
        self, left: Expression,
        operators: list, operands: list, lineno, col
    ):
        super().__init__(lineno, col)
        self.left = left
        self.operators = operators
        self.operands = operands
        
class BoolOp(Expression): # and, or
    def __init__(self, operator: Operator, operands: list, lineno, col):
        super().__init__(lineno, col)
        self.operator = operator
        self.operands = operands
        
class RawScore(Expression): # directly get the score on a scoreboard
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
    # Base class for AST handler
    def visit(self, node: AST, **kwargs):
        visitor = getattr(
            self,
            'visit_%s' % node.__class__.__name__,
            self.general_visit
        )
        return visitor(node, **kwargs)
    
    def general_visit(self, node: AST):
        raise NotImplementedError
