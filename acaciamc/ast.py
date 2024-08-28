"""Abstract Syntax Tree definitions for Acacia."""

from typing import (
    Union, List, Optional, Dict, Iterable, Tuple, Any, FrozenSet
)

from acaciamc.utils.str_template import DisplayableEnum

# --- AST components

class FuncQualifier(DisplayableEnum):
    """Function qualifiers."""

    none = 0, "runtime function"
    inline = 1, "inline function"
    const = 2, "compile time function"

class MethodQualifier(DisplayableEnum):
    """Entity method qualifiers."""

    none = 0, "(none)"
    virtual = 1, "virtual"
    override = 2, "override"
    static = 3, "static"

# --- AST node superclasses

# These fields are not considered a "children" of an AST:
RESERVED_FIELDS = frozenset((
    # For `HasSource`:
    'begin', 'end',
    # Public function in `AST`:
    'get_fields',
    # Annotation
    'annotation',
))

class AST:
    """Base class for Acacia's AST."""

    # See `get_fields`:
    _fields: Optional[Tuple[str, ...]] = None
    _fields_ignore: FrozenSet[str] = frozenset()
    # Extra information on this node (used by post AST visitor):
    annotation: Any = None

    def get_fields(self) -> Tuple[str, ...]:
        """Get the names of fields of a node."""
        cls = type(self)
        if cls._fields is None:
            cls._fields = tuple(
                name
                for name in dir(self)
                if (not name.startswith('_')
                    and name not in RESERVED_FIELDS
                    and name not in cls._fields_ignore)
            )
        return cls._fields

class HasSource(AST):
    """
    Indicate that this AST node has a corresponding range in source
    code.
    """

    def __init__(self, begin: Tuple[int, int], end: Tuple[int, int]):
        self.begin = begin
        self.end = end

# These classes are for classifying

class Statement(HasSource):
    pass

class Expression(HasSource):
    pass

# --- Special constructs

class IdentifierDef(HasSource):
    """
    An identifier with source info. Typically this is used to indicate
    this name is defined here (e.g. `VarDef` uses this).
    """

    def __init__(self, name: str, begin, end):
        super().__init__(begin, end)
        self.name = name

class Module(AST):
    """A module -- toplevel node."""

    def __init__(self, body: List[Statement]):
        self.body = body

class FormalParam(AST):
    def __init__(self, name: IdentifierDef, valpassing: "ValuePassing",
                 type_: Optional["TypeSpec"], default: Optional[Expression]):
        self.name = name
        self.valpassing = valpassing
        self.type = type_
        self.default = default

class CallTable(HasSource):
    """A collection of arguments when calling a function."""

    def __init__(self, args: List[Expression],
                 keywords: Dict[str, Expression], begin, end):
        super().__init__(begin, end)
        self.args = args
        self.keywords = keywords

class TypeSpec(AST):
    """Wraps an expression to indicate it is used as a type."""

    def __init__(self, content: Expression):
        self.content = content

class ReturnSpec(AST):
    def __init__(self, type_: TypeSpec, valpassing: "ValuePassing"):
        self.type = type_
        self.valpassing = valpassing

class FormattedStr(AST):
    """A literal string with formatted expressions like ${this}."""

    def __init__(self, content: List[Union[Expression, str]]):
        self.content = content

class ModuleMeta(HasSource):
    """A name of the module/package like "math" or "foo.bar"."""

    _fields_ignore = frozenset(("unparse",))

    def __init__(self, path: Iterable[str], begin, end):
        super().__init__(begin, end)
        self.path = list(path)
        assert self.path

    def unparse(self) -> str:
        """Return the normalized module name."""
        return ".".join(self.path)

# --- Enumeration

class UnaryOperator(HasSource):
    pass

class BinaryOperator(HasSource):
    pass

class ComparisonOperator(HasSource):
    pass

class BooleanOperator(AST):
    pass

class ValuePassing(HasSource):
    """
    Different kinds of value passing (used by parameters and return
    values).
    """

    _fields_ignore = frozenset(("display_name",))
    display_name: str

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

class PassByValue(ValuePassing):
    display_name = "(none)"
class PassByReference(ValuePassing):
    display_name = "&"
class PassConst(ValuePassing):
    display_name = "const"

# --- Statements (and their relevant constructs)

class ExprStatement(Statement):
    """A statement that contains just an unused expression."""

    def __init__(self, value: Expression):
        super().__init__(value.begin, value.end)
        self.value = value

class Pass(Statement):
    """No-op. Corresponds to the "pass" statement."""

    pass

class If(Statement):
    def __init__(
        self, condition: Expression,
        body: List[Statement], else_body: List[Statement], begin, end
    ):
        super().__init__(begin, end)
        self.condition = condition
        self.body = body
        self.else_body = else_body

class While(Statement):
    def __init__(self, condition: Expression,
                 body: List[Statement], begin, end):
        super().__init__(begin, end)
        self.condition = condition
        self.body = body

class FuncData(AST):
    """
    A function definition that only contains information about the
    function itself, and not the name bound to the function (like
    `FuncDef`).
    """

    def __init__(
        self, qualifier: FuncQualifier, params: List[FormalParam],
        body: List[Statement], returns: Optional[ReturnSpec]
    ):
        self.qualifier = qualifier
        self.params = params
        self.returns = returns
        self.body = body
        if __debug__:
            if qualifier is FuncQualifier.none and returns is not None:
                assert isinstance(returns.valpassing, PassByValue)
                assert returns.type is not None
            if qualifier is FuncQualifier.const:
                assert (returns is None
                        or not isinstance(returns.valpassing, PassConst))

class FuncDef(Statement):
    def __init__(self, name: IdentifierDef, data: FuncData, begin, end):
        super().__init__(begin, end)
        self.name = name
        self.data = data

class SimpleInterfacePath(HasSource):
    def __init__(self, value: str, begin, end):
        super().__init__(begin, end)
        self.value = value

class InterfaceDef(Statement):
    def __init__(self, path: Union[SimpleInterfacePath, "StrLiteral"],
                 body: List[Statement], begin, end):
        super().__init__(begin, end)
        self.path = path
        self.body = body

class EntityField(HasSource):
    def __init__(self, name: IdentifierDef, type_: TypeSpec, begin, end):
        super().__init__(begin, end)
        self.name = name
        self.type = type_

class EntityMethod(HasSource):
    def __init__(self, content: FuncDef,
                 qualifier: MethodQualifier, begin, end):
        super().__init__(begin, end)
        self.content = content
        self.qualifier = qualifier
        assert (content.data.qualifier is not FuncQualifier.const
                or qualifier is MethodQualifier.static)

class NewMethod(HasSource):
    """The "new" method in an entity template."""

    def __init__(self, data: FuncData, new_begin, new_end, begin, end):
        super().__init__(begin, end)
        self.data = data
        # These two are for diagnostics:
        self.new_begin = new_begin
        self.new_end = new_end
        assert data.qualifier is not FuncQualifier.const

class EntityTemplateDef(Statement):
    def __init__(
        self, name: IdentifierDef, parents: List[Expression],
        fields: List[EntityField], methods: List[EntityMethod],
        new_method: Optional[NewMethod],
        begin, end
    ):
        super().__init__(begin, end)
        self.name = name
        self.parents = parents
        self.fields = fields
        self.methods = methods
        self.new_method = new_method

class VarDef(Statement):
    """Variable definition using ":" and "="."""

    def __init__(self, target: IdentifierDef, type_: TypeSpec,
                 value: Optional[Expression], begin, end):
        super().__init__(begin, end)
        self.target = target
        self.type = type_
        self.value = value

class AutoVarDef(Statement):
    """Variable definition using ":=" (inferred type)."""

    def __init__(self, target: IdentifierDef, value: Expression, begin, end):
        super().__init__(begin, end)
        self.target = target
        self.value = value

class Assign(Statement):
    def __init__(self, target: Expression, value: Expression, begin, end):
        super().__init__(begin, end)
        self.target = target
        self.value = value

class CompileTimeAssign(AST):
    """Child node of `ConstDef` and `ReferenceDef`."""

    def __init__(self, name: IdentifierDef, type_: Optional[TypeSpec],
                 value: Expression):
        self.name = name
        self.type = type_
        self.value = value

class ConstDef(Statement):
    """A bunch of (not just a single) constant definitions."""

    def __init__(self, contents: List[CompileTimeAssign], begin, end):
        super().__init__(begin, end)
        self.contents = contents

class ReferenceDef(Statement):
    def __init__(self, content: CompileTimeAssign, begin, end):
        super().__init__(begin, end)
        self.content = content

class Command(Statement):
    def __init__(self, content: FormattedStr, begin, end):
        super().__init__(begin, end)
        self.content = content

class AugmentedAssign(Statement):
    def __init__(
        self, target: Expression, operator: BinaryOperator,
        value: Expression, begin, end
    ):
        super().__init__(begin, end)
        self.target = target
        self.operator = operator
        self.value = value

class Import(Statement):
    def __init__(self, meta: ModuleMeta, alias: IdentifierDef, begin, end):
        super().__init__(begin, end)
        self.meta = meta
        self.name = alias

class ImportItem(AST):
    """Child node of `FromImport`."""

    def __init__(self, name: IdentifierDef, alias: IdentifierDef):
        self.name = name
        self.alias = alias

class FromImport(Statement):
    def __init__(self, meta: ModuleMeta, items: List[ImportItem], begin, end):
        super().__init__(begin, end)
        self.meta = meta
        self.items = items

class FromImportAll(Statement):
    def __init__(self, meta: ModuleMeta, star_begin, star_end, begin, end):
        super().__init__(begin, end)
        self.meta = meta
        # These two are for diagnostics:
        self.star_begin = star_begin
        self.star_end = star_end

class For(Statement):
    def __init__(self, name: IdentifierDef, expr: Expression,
                 body: List[Statement], begin, end):
        super().__init__(begin, end)
        self.name = name
        self.expr = expr
        self.body = body

class StructField(HasSource):
    def __init__(self, name: IdentifierDef, type_: TypeSpec, begin, end):
        super().__init__(begin, end)
        self.name = name
        self.type = type_

class StructDef(Statement):
    def __init__(self, name: IdentifierDef, bases: List[Expression],
                 fields: List[StructField], begin, end):
        super().__init__(begin, end)
        self.name = name
        self.bases = bases
        self.fields = fields

class Return(Statement):
    def __init__(self, value: Optional[Expression], begin, end):
        super().__init__(begin, end)
        self.value = value

class NewCall(Statement):
    """
    "Template.new()" or "new()" call inside a "new" entity method.
    """

    def __init__(self, primary: Optional[Expression],
                 call_table: CallTable, begin, end):
        super().__init__(begin, end)
        self.primary = primary
        self.call_table = call_table

# --- Expressions

class IntLiteral(Expression):
    def __init__(self, value: int, begin, end):
        super().__init__(begin, end)
        self.value = value

class BoolLiteral(Expression):
    def __init__(self, value: bool, begin, end):
        super().__init__(begin, end)
        self.value = value

class NoneLiteral(Expression):
    pass

class FloatLiteral(Expression):
    def __init__(self, value: float, begin, end):
        super().__init__(begin, end)
        self.value = value

class StrLiteral(Expression):
    def __init__(self, content: FormattedStr, begin, end):
        super().__init__(begin, end)
        self.content = content

class Self(Expression):
    """The "self" keyword."""

    pass

class Identifier(Expression):
    """A reference to an identifier."""

    def __init__(self, name: str, begin, end):
        super().__init__(begin, end)
        self.name = name

class UnaryOp(Expression):
    def __init__(self, operator: UnaryOperator,
                 operand: Expression, begin, end):
        super().__init__(begin, end)
        self.operator = operator
        self.operand = operand

class BinOp(Expression):
    def __init__(self, left: Expression, operator: BinaryOperator,
                 right: Expression, begin, end):
        super().__init__(begin, end)
        self.left = left
        self.operator = operator
        self.right = right

class Call(Expression):
    def __init__(self, func: Expression, table: CallTable, begin, end):
        super().__init__(begin, end)
        self.func = func
        self.table = table

class Attribute(Expression):
    def __init__(self, object_: Expression, attr: str, begin, end):
        super().__init__(begin, end)
        self.object = object_
        self.attr = attr

class Subscript(Expression):
    def __init__(self, object_: Expression,
                 subscripts: List[Expression], begin, end):
        super().__init__(begin, end)
        self.object = object_
        self.subscripts = subscripts

class CompareOp(Expression):
    def __init__(
        self, left: Expression, operators: List[ComparisonOperator],
        operands: List[Expression], begin, end
    ):
        super().__init__(begin, end)
        self.left = left
        self.operators = operators
        self.operands = operands

class BoolOp(Expression):
    """The "and" and "or" operators."""

    def __init__(self, operator: BooleanOperator,
                 operands: List[Expression], begin, end):
        super().__init__(begin, end)
        self.operator = operator
        self.operands = operands

class ListDef(Expression):
    """A literal compile time list."""

    def __init__(self, items: List[Expression], begin, end):
        super().__init__(begin, end)
        self.items = items

class MapDef(Expression):
    """A literal compile time map."""

    def __init__(self, keys: List[Expression],
                 values: List[Expression], begin, end):
        super().__init__(begin, end)
        self.keys = keys
        self.values = values

# --- AST-related utilities

class ASTVisitor:
    """
    A base class that walks through the whole AST tree and calls a
    visitor function for every node found. The visitor function for
    a node of type `T` is named `visit_T`. If no visitor function is
    defined, `generic_visit` will be used.
    """

    def visit(self, node: AST, **kwargs) -> Any:
        visitor = getattr(
            self,
            'visit_%s' % node.__class__.__name__,
            self.generic_visit
        )
        return visitor(node, **kwargs)

    def child_visit(self, obj: object):
        """
        If `obj` is an `AST`, visit it.
        If `obj` is a list of `AST`, visit all the elements.
        If `obj` is a dictionary whose values are `AST` nodes, visit
        all the values.
        Otherwise, do nothing.
        """
        if isinstance(obj, AST):
            self.visit(obj)
        elif isinstance(obj, list):
            for x in obj:
                if isinstance(x, AST):
                    self.visit(x)
        elif isinstance(obj, dict):
            for x in obj.values():
                if isinstance(x, AST):
                    self.visit(x)

    def generic_visit(self, node: AST):
        """
        Called when a specific visitor function does not exist. This
        default implementation visits all the children of given node
        using `child_visit`.
        """
        for field in node.get_fields():
            self.child_visit(getattr(node, field))

class ASTVisualizer:
    """
    This class converts an AST node to string representation. Use
    `convert` method.
    """

    def __init__(self, indent=2):
        self.indent = indent

    def _convert(self, value, indent: int) -> str:
        res: List[str] = []
        indent_next = indent + self.indent
        if isinstance(value, AST):
            if isinstance(value, HasSource):
                location_str = "@%d:%d-%d:%d " % (*value.begin, *value.end)
            else:
                location_str = ""
            res.append(f'{location_str}{type(value).__name__}(\n')
            for field in value.get_fields():
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

    def convert(self, node: AST) -> str:
        """Make a string representation for given `node`."""
        return self._convert(node, indent=0)
