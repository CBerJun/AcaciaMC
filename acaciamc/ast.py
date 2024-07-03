"""Abstarct Syntax Tree definitions for Acacia."""

from typing import (
    Union as _Union, List as _List, Optional as _Optional, Dict as _Dict,
    Iterable as _Iterable, Tuple as _Tuple, Type as _Type
)
# Unfortunately typing.OrderedDict is not available in Python 3.6
from collections import OrderedDict as _OrderedDict

from acaciamc.utils.str_template import DisplayableEnum as _DisplayableEnum

####################
### AST CONTENTS ###
####################

class MethodQualifier(_DisplayableEnum):
    """Entity method qualifiers."""

    none = 0, "(none)"
    virtual = 1, "virtual"
    override = 2, "override"
    static = 3, "static"

class FuncPortType(_DisplayableEnum):
    """Function port types."""

    by_value = 0, "(none)"
    by_reference = 1, "&"
    const = 2, "const"

#################
### AST NODES ###
#################

class AST:
    """Base class for Acacia's AST."""

    pass

class HasSource(AST):
    """
    Indicate that this AST node has a corresponding range in source
    code.
    """

    def __init__(self, begin: _Tuple[int, int], end: _Tuple[int, int]):
        self.begin = begin
        self.end = end

# These classes are for classifying

class Statement(HasSource):
    pass

class Expression(HasSource):
    pass

# --- Special Constructs

class IdentifierDef(HasSource):  # an identifier with source info
    def __init__(self, name: str, begin, end):
        super().__init__(begin, end)
        self.name = name

class Module(AST):  # a module
    def __init__(self, body: _List[Statement]):
        self.body = body

class FormalParam(AST):  # used by ArgumentTable
    def __init__(self, name: IdentifierDef, port: "FunctionPort",
                 default: _Optional[Expression]):
        self.name = name
        self.port = port
        self.default = default

class ArgumentTable(AST):  # arguments used in function definition
    def __init__(self, params: _OrderedDict):
        # In fact, `params` is _OrderedDict[str, FormalParam]
        self.params = params

class CallTable(AST):  # call table
    def __init__(self, args: _List[Expression],
                 keywords: _Dict[str, Expression]):
        self.args = args
        self.keywords = keywords

class TypeSpec(AST):  # specify type of value `int`
    def __init__(self, content: Expression):
        self.content = content

class FunctionPort(HasSource):
    def __init__(self, type_: _Optional[TypeSpec],
                 port: FuncPortType, begin, end):
        super().__init__(begin, end)
        self.type = type_
        self.port = port

class FormattedStr(AST):  # a literal string with ${formatted exprs}
    def __init__(self, content: _List[_Union[Expression, str]]):
        self.content = content

class ModuleMeta(HasSource):
    """Specifies a module."""

    def __init__(self, path: _Iterable[str], begin, end):
        super().__init__(begin, end)
        self.path = list(path)
        assert self.path

    def unparse(self) -> str:
        """
        Return a normalized string that represents this module meta.
        """
        return ".".join(self.path)

# --- Operators

class UnaryOperator(HasSource):
    pass

class BinaryOperator(HasSource):
    pass

class ComparisonOperator(HasSource):
    pass

class BooleanOperator(AST):
    pass

class UnaryAdd(UnaryOperator):
    pass
class UnarySub(UnaryOperator):
    pass
class UnaryNot(UnaryOperator):
    pass

class Add(BinaryOperator):
    pass
class Sub(BinaryOperator):
    pass
class Mul(BinaryOperator):
    pass
class Div(BinaryOperator):
    pass
class Mod(BinaryOperator):
    pass

class Less(ComparisonOperator):
    pass
class LessEqual(ComparisonOperator):
    pass
class Greater(ComparisonOperator):
    pass
class GreaterEqual(ComparisonOperator):
    pass
class Equal(ComparisonOperator):
    pass
class NotEqual(ComparisonOperator):
    pass

class And(BooleanOperator):
    pass
class Or(BooleanOperator):
    pass

# --- Statements (and their relevant constructs)

class ExprStatement(Statement):  # a bare expression used as a statement
    def __init__(self, value: Expression):
        super().__init__(value.begin, value.end)
        self.value = value

class Pass(Statement):  # does nothing
    pass

class If(Statement):  # if statement
    def __init__(
        self, condition: Expression,
        body: _List[Statement], else_body: _List[Statement], begin, end
    ):
        super().__init__(begin, end)
        self.condition = condition
        self.body = body
        self.else_body = else_body

class While(Statement):  # while statement
    def __init__(self, condition: Expression,
                 body: _List[Statement], begin, end):
        super().__init__(begin, end)
        self.condition = condition
        self.body = body

class FuncData(AST):
    def __init__(
        self, arg_table: ArgumentTable,
        body: _List[Statement], returns: _Optional[FunctionPort]
    ):
        self.arg_table = arg_table
        self.returns = returns
        self.body = body

class FuncDef(Statement):  # function definition
    def __init__(self, name: IdentifierDef, data: FuncData, begin, end):
        super().__init__(begin, end)
        self.name = name
        self.data = data

class NormalFuncData(FuncData):
    def __init__(
        self, arg_table: ArgumentTable,
        body: _List[Statement], returns: _Optional[FunctionPort]
    ):
        super().__init__(arg_table, body, returns)
        if returns is not None:
            assert returns.port is FuncPortType.by_value
            assert returns.type is not None
            self.return_type = returns.type

class InlineFuncData(FuncData):
    pass

class ConstFuncData(FuncData):
    def __init__(
        self, arg_table: ArgumentTable,
        body: _List[Statement], returns: _Optional[FunctionPort]
    ):
        super().__init__(arg_table, body, returns)
        assert returns is None or returns.port is not FuncPortType.const

class InterfaceDef(Statement):  # define an interface
    def __init__(self, path: _Union[str, "StrLiteral"],
                 body: _List[Statement], begin, end):
        super().__init__(begin, end)
        self.path = path
        self.body = body

class EntityField(HasSource):  # entity field definition
    def __init__(self, name: IdentifierDef, type_: TypeSpec, begin, end):
        super().__init__(begin, end)
        self.name = name
        self.type = type_

class EntityMethod(HasSource):  # entity method definition
    def __init__(self, content: FuncDef,
                 qualifier: MethodQualifier, begin, end):
        super().__init__(begin, end)
        self.content = content
        self.qualifier = qualifier
        assert (not isinstance(content.data, ConstFuncData)
                or qualifier is MethodQualifier.static)

class NewMethod(HasSource):  # new method definition
    def __init__(self, data: _Union[NormalFuncData, InlineFuncData],
                 new_begin, new_end, begin, end):
        super().__init__(begin, end)
        self.data = data
        # These two are for diagnostics:
        self.new_begin = new_begin
        self.new_end = new_end

class EntityTemplateDef(Statement):  # entity statement
    def __init__(
        self, name: IdentifierDef, parents: _List[Expression],
        body: _List[_Union[EntityMethod, EntityField, Pass]],
        new_method: _Optional[NewMethod],
        begin, end
    ):
        super().__init__(begin, end)
        self.name = name
        self.parents = parents
        self.body = body
        self.new_method = new_method

class VarDef(Statement):  # x: y [= z] variable declaration
    def __init__(self, target: IdentifierDef, type_: TypeSpec,
                 value: _Optional[Expression], begin, end):
        super().__init__(begin, end)
        self.target = target
        self.type = type_
        self.value = value

class AutoVarDef(Statement):  # := short variable declaration
    def __init__(self, target: IdentifierDef, value: Expression, begin, end):
        super().__init__(begin, end)
        self.target = target
        self.value = value

class Assign(Statement):  # normal assign
    def __init__(self, target: Expression, value: Expression, begin, end):
        super().__init__(begin, end)
        self.target = target
        self.value = value

class CompileTimeAssign(AST):
    def __init__(self, name: IdentifierDef, type_: _Optional[TypeSpec],
                 value: Expression):
        self.name = name
        self.type = type_
        self.value = value

class ConstDef(Statement):  # constant definition
    def __init__(self, contents: _List[CompileTimeAssign], begin, end):
        super().__init__(begin, end)
        self.contents = contents

class ReferenceDef(Statement):  # reference definition
    def __init__(self, content: CompileTimeAssign, begin, end):
        super().__init__(begin, end)
        self.content = content

class Command(Statement):  # raw command
    def __init__(self, content: FormattedStr, begin, end):
        super().__init__(begin, end)
        self.content = content

class AugmentedAssign(Statement):  # augmented assign
    def __init__(
        self, target: Expression, operator: BinaryOperator,
        value: Expression, begin, end
    ):
        super().__init__(begin, end)
        self.target = target
        self.operator = operator
        self.value = value

class Import(Statement):  # import a module
    def __init__(self, meta: ModuleMeta, alias: IdentifierDef, begin, end):
        super().__init__(begin, end)
        self.meta = meta
        self.name = alias

class ImportItem(AST):  # used by FromImport
    def __init__(self, name: str, alias: IdentifierDef):
        self.name = name
        self.alias = alias

class FromImport(Statement):  # import specific things from a module
    def __init__(self, meta: ModuleMeta, items: _List[ImportItem], begin, end):
        super().__init__(begin, end)
        self.meta = meta
        self.items = items

class FromImportAll(Statement):  # import everything in a module
    def __init__(self, meta: ModuleMeta, star_begin, star_end, begin, end):
        super().__init__(begin, end)
        self.meta = meta
        # These two are for diagnostics:
        self.star_begin = star_begin
        self.star_end = star_end

class For(Statement):  # for-in iteration
    def __init__(self, name: IdentifierDef, expr: Expression,
                 body: _List[Statement], begin, end):
        super().__init__(begin, end)
        self.name = name
        self.expr = expr
        self.body = body

class StructField(HasSource):  # a struct's field
    def __init__(self, name: IdentifierDef, type_: TypeSpec, begin, end):
        super().__init__(begin, end)
        self.name = name
        self.type = type_

class StructDef(Statement):  # struct definition
    def __init__(self, name: IdentifierDef, bases: _List[Expression],
                 body: _List[_Union[StructField, Pass]], begin, end):
        super().__init__(begin, end)
        self.name = name
        self.bases = bases
        self.body = body

class Result(Statement):  # result xxx
    def __init__(self, value: Expression, begin, end):
        super().__init__(begin, end)
        self.value = value

class NewCall(Statement):  # Template.new() or new()
    def __init__(self, primary: _Optional[Expression],
                 call_table: CallTable, begin, end):
        super().__init__(begin, end)
        self.primary = primary
        self.call_table = call_table

# --- Expressions

class IntLiteral(Expression):  # integer literal like 10
    def __init__(self, value: int, begin, end):
        super().__init__(begin, end)
        self.value = value

class BoolLiteral(Expression):  # True, False
    def __init__(self, value: bool, begin, end):
        super().__init__(begin, end)
        self.value = value

class NoneLiteral(Expression):  # None
    pass

class FloatLiteral(Expression):  # float literals like 1.2
    def __init__(self, value: float, begin, end):
        super().__init__(begin, end)
        self.value = value

class StrLiteral(Expression):  # a string literal
    def __init__(self, content: FormattedStr, begin, end):
        super().__init__(begin, end)
        self.content = content

class Self(Expression):  # "self" keyword
    pass

class Identifier(Expression):  # an identifier
    def __init__(self, name: str, begin, end):
        super().__init__(begin, end)
        self.name = name

class UnaryOp(Expression):  # +x, -x, not x
    def __init__(self, operator: UnaryOperator,
                 operand: Expression, begin, end):
        super().__init__(begin, end)
        self.operator = operator
        self.operand = operand

class BinOp(Expression):  # an expr with binary operator (+, %, etc)
    def __init__(self, left: Expression, operator: BinaryOperator,
                 right: Expression, begin, end):
        super().__init__(begin, end)
        self.left = left
        self.operator = operator
        self.right = right

class Call(Expression):  # call an expression
    def __init__(self, func: Expression, table: CallTable, begin, end):
        super().__init__(begin, end)
        self.func = func
        self.table = table

class Attribute(Expression):  # attr of an expression
    def __init__(self, object_: Expression, attr: str, begin, end):
        super().__init__(begin, end)
        self.object = object_
        self.attr = attr

class Subscript(Expression):  # value[v1, v2]
    def __init__(self, object_: Expression,
                 subscripts: _List[Expression], begin, end):
        super().__init__(begin, end)
        self.object = object_
        self.subscripts = subscripts

class CompareOp(Expression):  # ==, !=, >, <, >=, <=
    def __init__(
        self, left: Expression, operators: _List[ComparisonOperator],
        operands: _List[Expression], begin, end
    ):
        super().__init__(begin, end)
        self.left = left
        self.operators = operators
        self.operands = operands

class BoolOp(Expression):  # and, or
    def __init__(self, operator: BooleanOperator,
                 operands: _List[Expression], begin, end):
        super().__init__(begin, end)
        self.operator = operator
        self.operands = operands

class ListDef(Expression):  # a literal compile time list
    def __init__(self, items: _List[Expression], begin, end):
        super().__init__(begin, end)
        self.items = items

class MapDef(Expression):  # a literal compile time map
    def __init__(self, keys: _List[Expression],
                 values: _List[Expression], begin, end):
        super().__init__(begin, end)
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

class ASTVisualizer:
    _fields_cache: _Dict[_Type[AST], _List[str]] = {}

    def __init__(self, node: AST, indent=2):
        self.node = node
        self.indent = indent

    @classmethod
    def get_fields(cls, node: AST) -> _List[str]:
        """Get the names of fields of a node."""
        tp = type(node)
        if tp not in cls._fields_cache:
            cls._fields_cache[tp] = [
                name for name in dir(node)
                if (
                    not name.startswith('_')
                    and name != 'begin'
                    and name != 'end'
                )
            ]
        return cls._fields_cache[tp]

    def _convert(self, value, indent: int = 0) -> str:
        res: _List[str] = []
        indent_next = indent + self.indent
        if isinstance(value, AST):
            if isinstance(value, HasSource):
                location_str = "@%d:%d-%d:%d " % (*value.begin, *value.end)
            else:
                location_str = ""
            res.append(f'{location_str}{type(value).__name__}(\n')
            for field in self.get_fields(value):
                fvalue = getattr(value, field)
                res.append('%s%s = %s\n' % (
                    ' ' * indent_next, field,
                    self._convert(fvalue, indent=indent_next)
                ))
            res.append('%s)' % (' ' * indent))
        elif isinstance(value, list):
            res.append('[\n')
            for element in value:
                sub = self._convert(element, indent=(indent + self.indent))
                res.append('%s%s\n' % (' ' * indent_next, sub))
            res.append('%s]' % (' ' * indent))
        elif isinstance(value, dict):
            res.append('{\n')
            for k, v in value.items():
                sub = self._convert(v, indent=(indent + self.indent))
                res.append('%s%r: %s\n' % (' ' * indent_next, k, sub))
            res.append('%s}' % (' ' * indent))
        else:
            res.append(repr(value))
        return "".join(res)

    def get_string(self) -> str:
        return self._convert(self.node)
