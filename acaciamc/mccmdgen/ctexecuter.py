__all__ = ['CTExecuter']

from contextlib import contextmanager
from typing import TYPE_CHECKING, Optional, List, Dict

from acaciamc.ast import *
from acaciamc.error import Error, ErrorType, SourceLocation
from acaciamc.mccmdgen.ctexpr import *
from acaciamc.mccmdgen.symbol import SymbolTable, CTRTConversionError
from acaciamc.mccmdgen.utils import unreachable, InvalidOpError
from acaciamc.objects import (
    IntLiteral, BoolLiteral, String, CTList, CTMap, NoneLiteral, Float
)

if TYPE_CHECKING:
    from acaciamc.mccmdgen.generator import Generator

BINOPS = {
    Operator.add: 'cadd',
    Operator.minus: 'csub',
    Operator.multiply: 'cmul',
    Operator.divide: 'cdiv',
    Operator.mod: 'cmod'
}
RBINOPS = {
    Operator.add: 'cradd',
    Operator.minus: 'crsub',
    Operator.multiply: 'crmul',
    Operator.divide: 'crdiv',
    Operator.mod: 'crmod'
}


class CTExecuter(ASTVisitor):
    def __init__(self, scope: SymbolTable, generator: "Generator",
                 file_name: str):
        super().__init__()
        self.generator = generator
        self.compiler = generator.compiler
        self.file_name = file_name
        self.builtins = generator.compiler.builtins
        self.current_scope = SymbolTable(scope, self.builtins)
        self.result: Optional[CTExpr] = None
        self.curnode: Optional[AST] = None

    def visit(self, node: AST, **kwds):
        oldnode = self.curnode
        self.curnode = node
        res = super().visit(node, **kwds)
        self.curnode = oldnode
        return res

    def visittop(self, node: AST, **kwds):
        try:
            return self.visit(node, **kwds)
        except Error as e:
            if not e.location.linecol_set():
                e.location.linecol = (self.curnode.lineno, self.curnode.col)
            raise

    def node_location(self, node: AST):
        return SourceLocation(self.file_name, (node.lineno, node.col))

    def error_node(self, node: AST, *args, **kwds):
        err = Error(*args, **kwds)
        # `err.location.file` is to be done by `Generator`
        err.location.linecol = (node.lineno, node.col)
        raise err

    def general_visit(self, node: AST):
        self.error_node(node, ErrorType.INVALID_CONST_STMT)

    @contextmanager
    def new_scope(self):
        self.current_scope = SymbolTable(self.current_scope, self.builtins)
        yield
        self.current_scope = self.current_scope.outer

    def register_symbol(self, name: str, value: CTExpr):
        v = self.current_scope.clookup(
            name, use_outer=False, use_builtins=False
        )
        if v is not None:
            self.error_node(self.curnode, ErrorType.SHADOWED_NAME, name=name)
        self.current_scope.set(name, value)

    ## Expression visitors

    def visit_Literal(self, node: Literal):
        value = node.value
        # NOTE Python bool is a subclass of int!!!
        if isinstance(value, bool):
            return BoolLiteral(value)
        elif isinstance(value, int):
            return IntLiteral(value)
        elif value is None:
            r = NoneLiteral()
            r.is_temporary = True
            return r
        elif isinstance(value, float):
            return Float(value)
        unreachable()

    def visit_StrLiteral(self, node: StrLiteral):
        s = self.visit(node.content)
        return String(s)

    def visit_Self(self, node: Self):
        self.error_node(node, ErrorType.SELF_OUT_OF_SCOPE)

    def visit_ListDef(self, node: ListDef):
        return CTList(map(self.visit, node.items))

    def visit_MapDef(self, node: MapDef):
        return CTMap(map(self.visit, node.keys),
                     map(self.visit, node.values))

    def visit_Identifier(self, node: Identifier):
        name = node.name
        try:
            v = self.current_scope.clookup(name)
        except CTRTConversionError as err:
            self.error_node(node, ErrorType.NOT_CONST_NAME, name=name,
                            type_=str(err.expr.data_type))
        if v is None:
            self.error_node(node, ErrorType.NAME_NOT_DEFINED, name=name)
        return v

    def attribute_of(self, primary: CTExpr, attr: str):
        primary = abs(primary)
        try:
            v = primary.attributes.clookup(attr)
        except CTRTConversionError as err:
            self.error_node(self.curnode, ErrorType.NOT_CONST_ATTR,
                            attr=attr, type_=str(err.expr.data_type),
                            primary=primary.cdata_type.name)
        if v is None:
            self.error_node(
                self.curnode,
                ErrorType.HAS_NO_ATTRIBUTE,
                value_type=primary.cdata_type.name, attr=attr
            )
        return v

    def visit_Attribute(self, node: Attribute):
        obj: CTObj = abs(self.visit(node.object))
        return self.attribute_of(obj, node.attr)

    def visit_UnaryOp(self, node: UnaryOp):
        obj: CTObj = abs(self.visit(node.operand))
        if node.operator is Operator.not_:
            meth = obj.cunarynot
        elif node.operator is Operator.positive:
            meth = obj.cunarypos
        elif node.operator is Operator.negative:
            meth = obj.cunaryneg
        else:
            unreachable()
        try:
            return meth()
        except InvalidOpError:
            self.error_node(node, ErrorType.INVALID_OPERAND,
                            operator=node.operator.value,
                            operand=f'"{obj.cdata_type.name}"')

    def visit_BinOp(self, node: BinOp):
        left: CTObj = abs(self.visit(node.left))
        right: CTObj = abs(self.visit(node.right))
        try:
            res = getattr(left, BINOPS[node.operator])(right)
        except InvalidOpError:
            try:
                res = getattr(right, RBINOPS[node.operator])(left)
            except InvalidOpError:
                ls = left.cdata_type.name
                rs = right.cdata_type.name
                self.error_node(
                    node, ErrorType.INVALID_OPERAND,
                    operator=node.operator.value,
                    operand=f'"{ls}", "{rs}"'
                )
        return res

    def visit_CompareOp(self, node: CompareOp):
        operands = map(self.visit, node.operands)
        left, right = None, abs(self.visit(node.left))
        final = True
        for operator, operand in zip(node.operators, operands):
            left, right = right, abs(operand)
            try:
                res = left.ccompare(operator, right)
            except InvalidOpError:
                try:
                    res = right.ccompare(COMPOP_SWAP[operator], left)
                except InvalidOpError:
                    ls = left.cdata_type.name
                    rs = right.cdata_type.name
                    self.error_node(
                        node, ErrorType.INVALID_OPERAND,
                        operator=operator.value,
                        operand=f'"{ls}", "{rs}"'
                    )
            if not res:
                final = False
        return BoolLiteral(final)

    def visit_BoolOp(self, node: BoolOp):
        operands: List[CTObj] = [
            abs(self.visit(operand)) for operand in node.operands
        ]
        operator = node.operator
        res = operator is Operator.and_
        for i, operand in enumerate(operands):
            if not isinstance(operand, BoolLiteral):
                self.error_node(
                    node.operands[i],
                    ErrorType.INVALID_BOOLOP_OPERAND,
                    operator=operator.value,
                    operand=operand.cdata_type.name
                )
            if operand.value and operator is Operator.or_:
                res = True
            elif not operand.value and operator is Operator.and_:
                res = False
        return BoolLiteral(res)

    def visit_Call(self, node: Call):
        func: CTObj = abs(self.visit(node.func))
        if not isinstance(func, CTCallable):
            self.error_node(node, ErrorType.UNCALLABLE,
                            expr_type=func.cdata_type.name)
        args, keywords = self.visit(node.table)
        return func.ccall_withframe(
            args, keywords, self.compiler,
            self.node_location(node)
        )

    def visit_Subscript(self, node: Subscript):
        obj: CTObj = abs(self.visit(node.object))
        subscripts = list(map(self.visit, node.subscripts))
        meth = self.attribute_of(obj, "__ct_getitem__")
        if meth is None:
            self.error_node(node, ErrorType.NO_GETITEM,
                            type_=obj.cdata_type.name)
        meth = abs(meth)
        if not isinstance(meth, CTCallable):
            self.error_node(node, ErrorType.UNCALLABLE,
                            expr_type=obj.cdata_type.name)
        return meth.ccall_withframe(
            subscripts, {}, self.compiler,
            self.node_location(node)
        )

    ## Statement visitors

    def visit_VarDef(self, node: VarDef):
        if node.value is None:
            self.error_node(node, ErrorType.UNINITIALIZED_CONST)
        dt: CTDataType = self.visit(node.type)
        value: CTObj = abs(self.visit(node.value))
        if not dt.is_typeof(value):
            self.error_node(node.type, ErrorType.WRONG_ASSIGN_TYPE,
                            got=value.cdata_type.name, expect=dt.name)
        self.register_symbol(node.target, CTObjPtr(value))

    def visit_AutoVarDef(self, node: AutoVarDef):
        value: CTObj = abs(self.visit(node.value))
        self.register_symbol(node.target, CTObjPtr(value))

    def visit_Assign(self, node: Assign):
        target: CTExpr = self.visit(node.target)
        if not isinstance(target, CTObjPtr):
            self.error_node(node.target, ErrorType.INVALID_ASSIGN_TARGET)
        value: CTObj = abs(self.visit(node.value))
        target.set(value)

    def visit_AugmentedAssign(self, node: AugmentedAssign):
        # A += B during compile time is implemented just as A = A + B
        target: CTExpr = self.visit(node.target)
        if not isinstance(target, CTObjPtr):
            self.error_node(node.target, ErrorType.INVALID_ASSIGN_TARGET)
        value: CTObj = abs(self.visit(node.value))
        try:
            res = getattr(abs(target), BINOPS[node.operator])(value)
        except InvalidOpError:
            t1 = abs(target).cdata_type.name
            t2 = value.cdata_type.name
            self.error_node(node, ErrorType.INVALID_OPERAND,
                            operator=f'{node.operator.value}=',
                            operand=f'"{t1}", "{t2}"')
        target.set(res)

    def visit_ReferenceDef(self, node: ReferenceDef):
        value: CTExpr = self.visit(node.value)
        if not isinstance(value, CTObjPtr):
            self.error_node(node.value, ErrorType.CANT_REF)
        if node.type is not None:
            dt: CTDataType = self.visit(node.type)
            if not dt.is_typeof(value):
                self.error_node(node.type, ErrorType.WRONG_REF_TYPE,
                                anno=dt.name, got=value.cdata_type.name)
        self.register_symbol(node.name, value)

    def visit_ExprStatement(self, node: ExprStatement):
        self.visit(node.value)

    def visit_Pass(self, node: Pass):
        pass

    def visit_If(self, node: If):
        condition: CTObj = abs(self.visit(node.condition))
        if not isinstance(condition, BoolLiteral):
            self.error_node(node.condition, ErrorType.WRONG_IF_CONDITION,
                            got=condition.cdata_type.name)
        running = node.body if condition.value else node.else_body
        for stmt in running:
            self.visit(stmt)

    def visit_While(self, node: While):
        def _while_cond() -> bool:
            condition: CTObj = abs(self.visit(node.condition))
            if not isinstance(condition, BoolLiteral):
                self.error_node(
                    node.condition, ErrorType.WRONG_WHILE_CONDITION,
                    got=condition.cdata_type.name
                )
            return condition.value

        while _while_cond():
            for stmt in node.body:
                self.visit(stmt)

    def visit_For(self, node: For):
        iterable: CTObj = abs(self.visit(node.expr))
        try:
            values = iterable.citerate()
        except InvalidOpError:
            self.error_node(
                node.expr, ErrorType.NOT_ITERABLE,
                type_=iterable.cdata_type.name
            )
        for value in values:
            with self.new_scope():
                self.register_symbol(node.name, abs(value))
                for stmt in node.body:
                    self.visit(stmt)

    def visit_Result(self, node: Result):
        # Toplevel result
        self.result = self.visit(node.value)

    # TODO compile time struct?

    # Imports are not supported (so far) because compile time functions
    # are supposed to have no side effects, but parsing a module may
    # produce commands or change runtime variables.

    # Nested functions and entity templates are not supported (so far)
    # because using symbols from current scope in nested functions could
    # cause unexpected results (e.g. using symbols in runtime function
    # and inline/const function may lead to different results).

    ## Other visitors

    def visit_TypeSpec(self, node: TypeSpec) -> CTDataType:
        type_: CTObj = abs(self.visit(node.content))
        try:
            dt = type_.cdatatype_hook()
        except InvalidOpError:
            self.error_node(node, ErrorType.INVALID_TYPE_SPEC,
                            got=type_.cdata_type.name)
        return dt

    def visit_CallTable(self, node: CallTable):
        args: List[CTExpr] = []
        keywords: Dict[str, CTExpr] = {}
        for value in node.args:
            args.append(self.visit(value))
        for arg, value in node.keywords.items():
            keywords[arg] = self.visit(value)
        return args, keywords

    def visit_FormattedStr(self, node: FormattedStr) -> str:
        res: List[str] = []
        for section in node.content:
            if isinstance(section, str):
                res.append(section)
            else:
                expr: CTObj = abs(self.visit(section))
                try:
                    value = expr.cstringify()
                except InvalidOpError:
                    self.error_node(section, ErrorType.INVALID_FEXPR)
                res.append(value)
        return ''.join(res)
