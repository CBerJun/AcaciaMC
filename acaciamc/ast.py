"""Abstarct Syntax Tree definitions for Acacia."""

from typing import (
    Union as _Union, List as _List, Optional as _Optional, Dict as _Dict,
    Iterable as _Iterable
)

from acaciamc.localization import LocalizedEnum as _LocalizedEnum


####################
### AST CONTENTS ###
####################

class Operator(_LocalizedEnum):
    # unary
    positive = "ast.operator.positive"
    negative = "ast.operator.negative"
    not_ = "ast.operator.not"
    # binary
    multiply = "ast.operator.multiply"
    divide = "ast.operator.divide"
    mod = "ast.operator.mod"
    add = "ast.operator.add"
    minus = "ast.operator.minus"
    # compare
    equal_to = "ast.operator.equal_to"
    unequal_to = "ast.operator.unequal_to"
    greater = "ast.operator.greater"
    less = "ast.operator.less"
    greater_equal = "ast.operator.greater_equal"
    less_equal = "ast.operator.less_equal"
    # boolean
    and_ = "ast.operator.and"
    or_ = "ast.operator.or"


COMPOP_INVERT = {
    # Used to invert ("not") a comparison
    Operator.greater: Operator.less_equal,
    Operator.greater_equal: Operator.less,
    Operator.less: Operator.greater_equal,
    Operator.less_equal: Operator.greater,
    Operator.equal_to: Operator.unequal_to,
    Operator.unequal_to: Operator.equal_to
}
COMPOP_SWAP = {
    # Used to swap the operands of a comparison
    Operator.greater: Operator.less,
    Operator.greater_equal: Operator.less_equal,
    Operator.less: Operator.greater,
    Operator.less_equal: Operator.greater_equal,
    Operator.equal_to: Operator.equal_to,
    Operator.unequal_to: Operator.unequal_to
}


class MethodQualifier(_LocalizedEnum):
    """Entity method qualifiers."""

    none = "ast.methodqualifier.none"
    virtual = "ast.methodqualifier.virtual"
    override = "ast.methodqualifier.override"
    static = "ast.methodqualifier.static"


class FuncPortType(_LocalizedEnum):
    """Function port types."""

    by_value = "ast.funcporttype.by_value"
    by_reference = "ast.funcporttype.by_reference"
    const = "ast.funcporttype.const"


class ModuleMeta:
    """Specifies a module."""

    def __init__(self, last_name: str, leading_dots: int = 0,
                 parents: _Iterable[str] = ()):
        self.leading_dots = leading_dots
        self.last_name = last_name
        self.parents = list(parents)

    def __str__(self) -> str:
        return ("." * self.leading_dots
                + ".".join(self.parents)
                + ("." if self.parents else "")
                + self.last_name)

    def __repr__(self) -> str:
        return "<ModuleMeta %r>" % str(self)


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
    def __init__(self, body: _List[Statement], lineno, col):
        super().__init__(lineno, col)
        self.body = body


class ArgumentTable(AST):  # arguments used in function definition
    show_debug = False

    def __init__(self, lineno, col):
        super().__init__(lineno, col)
        self.args: _List[str] = []  # argument names
        self.default: _Dict[str, _Optional[Expression]] = {}
        self.types: _Dict[str, FunctionPort] = {}

    def add_arg(self, name: str, type_: "FunctionPort",
                default: _Optional[Expression]):
        self.args.append(name)
        self.types[name] = type_
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


class FunctionPort(AST):
    show_debug = False

    def __init__(self, type_: _Optional[TypeSpec],
                 port: FuncPortType, lineno, col):
        super().__init__(lineno, col)
        self.type = type_
        self.port = port


class FormattedStr(AST):  # a literal string with ${formatted exprs}
    show_debug = False

    def __init__(self, content: _List[_Union[Expression, str]], lineno, col):
        super().__init__(lineno, col)
        self.content = content


class ExprStatement(Statement):  # a statement that is an expression
    def __init__(self, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.value = value


class Pass(Statement):  # does nothing
    pass


class If(Statement):  # if statement
    def __init__(
            self, condition: Expression,
            body: _List[Statement], else_body: _List[Statement], lineno, col
    ):
        super().__init__(lineno, col)
        self.condition = condition
        self.body = body
        self.else_body = else_body


class While(Statement):  # while statement
    def __init__(self, condition: Expression,
                 body: _List[Statement], lineno, col):
        super().__init__(lineno, col)
        self.condition = condition
        self.body = body


class FuncData(AST):
    show_debug = False


class FuncDef(Statement):  # function definition
    def __init__(self, name: str, data: FuncData, lineno, col):
        super().__init__(lineno, col)
        self.name = name
        self.data = data


class NormalFuncData(FuncData):
    def __init__(
            self, arg_table: ArgumentTable,
            body: _List[Statement], returns: _Optional[FunctionPort], lineno, col
    ):
        super().__init__(lineno, col)
        self.arg_table = arg_table
        if returns is None:
            self.returns = None
        else:
            assert returns.port is FuncPortType.by_value
            assert returns.type is not None
            self.returns = returns.type
        self.body = body


class InlineFuncData(FuncData):
    def __init__(
            self, arg_table: ArgumentTable,
            body: _List[Statement], returns: _Optional[FunctionPort], lineno, col
    ):
        super().__init__(lineno, col)
        self.arg_table = arg_table
        self.returns = returns
        self.body = body


class ConstFuncData(FuncData):
    def __init__(
            self, arg_table: ArgumentTable,
            body: _List[Statement], returns: _Optional[FunctionPort], lineno, col
    ):
        super().__init__(lineno, col)
        self.arg_table = arg_table
        self.returns = returns
        self.body = body
        assert returns is None or returns.port is not FuncPortType.const


class InterfaceDef(Statement):  # define an interface
    def __init__(self, path: _Union[str, "StrLiteral"],
                 body: _List[Statement], lineno, col):
        super().__init__(lineno, col)
        self.path = path
        self.body = body


class EntityField(Statement):  # entity field definition
    def __init__(self, name: str, type_: TypeSpec, lineno, col):
        super().__init__(lineno, col)
        self.name = name
        self.type = type_


class EntityMethod(Statement):  # entity method definition
    def __init__(self, content: FuncDef,
                 qualifier: MethodQualifier, lineno, col):
        super().__init__(lineno, col)
        self.content = content
        self.qualifier = qualifier
        assert (not isinstance(content.data, ConstFuncData)
                or qualifier is MethodQualifier.static)


class NewMethod(Statement):  # new method definition
    def __init__(self, data: _Union[NormalFuncData, InlineFuncData],
                 lineno, col):
        super().__init__(lineno, col)
        self.data = data


class EntityTemplateDef(Statement):  # entity statement
    def __init__(
            self, name: str, parents: _List[Expression],
            body: _List[_Union[EntityMethod, EntityField, Pass]],
            new_method: _Optional[NewMethod],
            lineno, col
    ):
        super().__init__(lineno, col)
        self.name = name
        self.parents = parents
        self.body = body
        self.new_method = new_method


class VarDef(Statement):  # x: y [= z] variable declaration
    def __init__(self, target: str, type_: TypeSpec,
                 value: _Optional[Expression], lineno, col):
        super().__init__(lineno, col)
        self.target = target
        self.type = type_
        self.value = value


class AutoVarDef(Statement):  # := short variable declaration
    def __init__(self, target: str, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.target = target
        self.value = value


class Assign(Statement):  # normal assign
    def __init__(self, target: Expression, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.target = target
        self.value = value


class ConstDef(Statement):  # constant definition
    def __init__(self, names: _List[str], types: _List[_Optional[TypeSpec]],
                 values: _List[Expression], lineno, col):
        super().__init__(lineno, col)
        self.names = names
        self.types = types
        self.values = values


class ReferenceDef(Statement):  # reference definition
    def __init__(self, name: str, type_: _Optional[TypeSpec],
                 value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.name = name
        self.type = type_
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


class Import(Statement):  # import a module
    def __init__(self, meta: ModuleMeta, alias: _Optional[str], lineno, col):
        super().__init__(lineno, col)
        self.meta = meta
        self.name = self.meta.last_name if alias is None else alias


class FromImport(Statement):  # import specific things from a module
    def __init__(
            self, meta: ModuleMeta, names: _List[str],
            aliases: _List[_Optional[str]], lineno, col
    ):
        super().__init__(lineno, col)
        self.meta = meta
        self.id2name: _Dict[str, str] = {}
        for name, alias in zip(names, aliases):
            self.id2name[name] = name if alias is None else alias


class FromImportAll(Statement):  # import everything in a module
    def __init__(self, meta: ModuleMeta, lineno, col):
        super().__init__(lineno, col)
        self.meta = meta


class For(Statement):  # for-in iteration
    def __init__(self, name: str, expr: Expression,
                 body: _List[Statement], lineno, col):
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


class Result(Statement):  # result xxx
    def __init__(self, value: Expression, lineno, col):
        super().__init__(lineno, col)
        self.value = value


class NewCall(Statement):  # Template.new() or new()
    def __init__(self, primary: _Optional[Expression],
                 call_table: CallTable, lineno, col):
        super().__init__(lineno, col)
        self.primary = primary
        self.call_table = call_table


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


class Identifier(Expression):  # an identifier
    def __init__(self, name: str, lineno, col):
        super().__init__(lineno, col)
        self.name = name


class UnaryOp(Expression):  # +x, -x, not x
    def __init__(self, operator: Operator, operand: Expression, lineno, col):
        super().__init__(lineno, col)
        self.operator = operator
        self.operand = operand


class BinOp(Expression):  # an expr with binary operator (+, %, >=, etc)
    def __init__(self, left: Expression, operator: Operator,
                 right: Expression, lineno, col):
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
    def __init__(self, object_: Expression,
                 subscripts: _List[Expression], lineno, col):
        super().__init__(lineno, col)
        self.object = object_
        self.subscripts = subscripts


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


class ListDef(Expression):  # a literal compile time list
    def __init__(self, items: _List[Expression], lineno, col):
        super().__init__(lineno, col)
        self.items = items


class MapDef(Expression):  # a literal compile time map
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
