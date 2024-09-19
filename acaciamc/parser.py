"""Parser for Acacia."""

from typing import (
    Callable, Optional, List, Tuple, NamedTuple, Type, Mapping, Union, Dict,
    Generator, TYPE_CHECKING
)
from collections import OrderedDict
from enum import Enum

from acaciamc.reader import LineCol, LineColRange
from acaciamc.tokenizer import TokenType, BRACKETS
from acaciamc.diagnostic import Diagnostic, DiagnosticError
from acaciamc.utils.str_template import STArgument, STStr, STEnum
import acaciamc.ast as ast

if TYPE_CHECKING:
    from acaciamc.tokenizer import Tokenizer, Token

COMPARE_OP_TOKENS: Mapping[TokenType, Type[ast.ComparisonOperator]] = {
    TokenType.equal_to: ast.Equal,
    TokenType.unequal_to: ast.NotEqual,
    TokenType.greater: ast.Greater,
    TokenType.less: ast.Less,
    TokenType.greater_equal: ast.GreaterEqual,
    TokenType.less_equal: ast.LessEqual,
}
UNARY_OP_TOKENS: Mapping[TokenType, Type[ast.UnaryOperator]] = {
    TokenType.plus: ast.UnaryAdd,
    TokenType.minus: ast.UnarySub,
}
BIN_OP_TOKENS1: Mapping[TokenType, Type[ast.BinaryOperator]] = {
    TokenType.star: ast.Mul,
    TokenType.slash: ast.Div,
    TokenType.mod: ast.Mod,
}
BIN_OP_TOKENS2: Mapping[TokenType, Type[ast.BinaryOperator]] = {
    TokenType.plus: ast.Add,
    TokenType.minus: ast.Sub,
}
AUG_ASSIGN_TOKENS: Mapping[TokenType, Type[ast.BinaryOperator]] = {
    TokenType.plus_equal: ast.Add,
    TokenType.minus_equal: ast.Sub,
    TokenType.times_equal: ast.Mul,
    TokenType.divide_equal: ast.Div,
    TokenType.mod_equal: ast.Mod,
}

class FuncType(NamedTuple):
    allowed_valpassing: Tuple[Type[ast.ValuePassing], ...]
    type_required: bool
    qualifier: ast.FuncQualifier

FUNC_NORMAL = FuncType(
    allowed_valpassing=(ast.PassByValue,),
    type_required=True,
    qualifier=ast.FuncQualifier.none
)
FUNC_INLINE = FuncType(
    allowed_valpassing=(ast.PassByValue, ast.PassByReference, ast.PassConst),
    type_required=False,
    qualifier=ast.FuncQualifier.inline
)
FUNC_CONST = FuncType(
    allowed_valpassing=(ast.PassByValue,),
    type_required=False,
    qualifier=ast.FuncQualifier.const
)

class STToken(STArgument):
    """Displays a `Token` to user."""

    def __init__(self, token: "Token"):
        self.token = token

    def process(self, metadata: str) -> str:
        assert not metadata
        return self.token.display_string()

class Scope(Enum):
    """
    To implement some of the checking, the parser has to keep track when
    it enters a function or an interface.
    """

    TOPLEVEL = 0
    FUNCTION = 1
    INTERFACE = 2

class Parser:
    """
    The parser takes in a stream of tokens and converts them to an AST.
    """

    def __init__(self, tokenizer: "Tokenizer"):
        self.tokenizer = tokenizer
        self.current_token = self.tokenizer.get_next_token()
        self.next_token: Optional["Token"] = None
        self.prev_token: Optional["Token"] = None
        self.scopes: List[Scope] = [Scope.TOPLEVEL]
        # These are statements that start with special token:
        self.token_to_complex_stmt = {
            TokenType.if_: self.if_stmt,
            TokenType.while_: self.while_stmt,
            TokenType.interface: self.interface_stmt,
            TokenType.def_: self.def_stmt,
            TokenType.inline: self.inline_def_stmt,
            TokenType.entity: self.entity_stmt,
            TokenType.for_: self.for_stmt,
            TokenType.struct: self.struct_stmt
        }
        self.token_to_simple_stmt = {
            TokenType.pass_: self.pass_stmt,
            TokenType.command_begin: self.command_stmt,
            TokenType.import_: self.import_stmt,
            TokenType.from_: self.from_import_stmt,
            TokenType.ampersand: self.reference_def_stmt,
            TokenType.return_: self.return_stmt,
            TokenType.new: self.simple_new_stmt
        }

    @property
    def current_range(self) -> LineColRange:
        """Range of current token."""
        return self.current_token.pos1, self.current_token.pos2

    @property
    def current_pos1(self) -> LineCol:
        """Begin of current token."""
        return self.current_token.pos1

    @property
    def prev_pos2(self) -> LineCol:
        """End of previous token."""
        assert self.prev_token
        return self.prev_token.pos2

    def error(
        self, diag_id: str, token: Optional["Token"] = None,
        args: Optional[Mapping[str, STArgument]] = None
    ):
        """
        Raise an ERROR diagnostic using the range in `token` as source
        range. If not given, use `current_token`.
        """
        if token is None:
            token = self.current_token
        raise DiagnosticError(
            self.diag_obj(diag_id, token.pos1, token.pos2, args)
        )

    def error_range(self, diag_id: str, pos1: LineCol, pos2: LineCol,
                    args: Optional[Mapping[str, STArgument]] = None):
        """Raise an `DiagnosticError`."""
        raise DiagnosticError(self.diag_obj(diag_id, pos1, pos2, args))

    def diag_obj(self, diag_id: str, pos1: LineCol, pos2: LineCol,
                 args: Optional[Mapping[str, STArgument]] = None):
        """Helper to create a `Diagnostic`."""
        if args is None:
            args = {}
        return Diagnostic(
            diag_id, self.tokenizer.file_entry, (pos1, pos2), args
        )

    def unexpected_token(self):
        """Raise an 'unexpected-token' ERROR on current token."""
        self.error('unexpected-token',
                   args={'token': STToken(self.current_token)})

    def eat(self, expect_token_type: Optional[TokenType] = None):
        """
        Move to next token. If `expect_token_type` is given, check if
        `current_token` has that type before moving, and raise error if
        not.
        """
        if ((expect_token_type is not None) and
            (self.current_token.type is not expect_token_type)):
            self.unexpected_token()
        self.prev_token = self.current_token
        if self.next_token is None:
            self.current_token = self.tokenizer.get_next_token()
        else:
            self.current_token = self.next_token
            self.next_token = None

    def peek(self):
        """Peek the next token and store at `self.next_token`."""
        if self.next_token is None:
            # only generate when not generated yet
            self.next_token = self.tokenizer.get_next_token()

    def indented_block(self) -> Generator[None, None, None]:
        """
        Read structures in an indented block.

        Usage::

            for _ in self.indented_block():
                read_structure()

        `read_structure` will be invoked repeatedly while we are still
        in this indented block. `read_structure` will be invoked at
        least once. An error is raised if there is no indented block.

        block_of{n} := NEW_LINE INDENT n+ DEDENT
        """
        self.eat(TokenType.new_line)
        newline_token = self.prev_token
        if self.current_token.type is not TokenType.indent:
            self.error('empty-block', newline_token)
        self.eat()  # INDENT
        if self.current_token.type is TokenType.dedent:
            # Is this (INDENT immediately followed by DEDENT) possible?
            # Well, it is! Consider this:
            # def foo():
            #     \
            #        # yep, a backslash followed by an empty line
            self.error('empty-block', newline_token)
        while self.current_token.type is not TokenType.dedent:
            yield
        self.eat()  # DEDENT

    def list_of(self, content: Callable[[], None]):
        """list_of{g} := g (COMMA g)*"""
        content()
        while self.current_token.type is TokenType.comma:
            self.eat()
            content()

    def paren_list_of(self, content: Callable[[], None],
                      lparen=TokenType.lparen):
        """paren_list_of{lp, g, rp} := lp (g COMMA)* g? rp"""
        self.eat(lparen)
        rp = BRACKETS[lparen]
        while self.current_token.type is not rp:
            content()
            if self.current_token.type is TokenType.comma:
                self.eat()
            else:
                break
        self.eat(rp)

    def statement_block(self) -> List[ast.Statement]:
        """
        Read a block of statements.
        statement_block := block_of{statement}
        """
        res: List[ast.Statement] = []
        for _ in self.indented_block():
            res.append(self.statement())
        return res

    # Following are different AST generators
    ## Expression generator

    def str_literal(self):
        """str_literal := (STRING_BEGIN formatted_str STRING_END)+"""
        content: List[Union[str, ast.Expression]] = []
        pos1 = self.current_pos1
        while self.current_token.type is TokenType.string_begin:
            self.eat()  # eat STRING_BEGIN
            content.extend(self.formatted_str().content)
            self.eat(TokenType.string_end)
        return ast.StrLiteral(
            ast.FormattedStr(content), begin=pos1, end=self.prev_pos2
        )

    def list_or_map(self):
        """
        list := paren_list_of{LBRACE, expr, RBRACE}
        map_item := expr COLON expr
        map := LBRACE ((map_item (COMMA map_item)* COMMA?) | COLON)
            RBRACE
        """
        pos1 = self.current_pos1
        self.eat(TokenType.lbrace)
        # Check for empty list or map
        if self.current_token.type is TokenType.rbrace:
            self.eat()
            return ast.ListDef(items=[], begin=pos1, end=self.prev_pos2)
        elif self.current_token.type is TokenType.colon:
            self.eat()
            self.eat(TokenType.rbrace)
            return ast.MapDef(
                keys=[], values=[], begin=pos1, end=self.prev_pos2
            )
        first = self.expr()
        if self.current_token.type is TokenType.colon:
            # Map
            self.eat()
            keys = [first]
            values = [self.expr()]
            if self.current_token.type is TokenType.comma:
                self.eat()
                while self.current_token.type is not TokenType.rbrace:
                    keys.append(self.expr())
                    self.eat(TokenType.colon)
                    values.append(self.expr())
                    if self.current_token.type is TokenType.comma:
                        self.eat()
                    else:
                        break
            self.eat(TokenType.rbrace)
            return ast.MapDef(keys, values, begin=pos1, end=self.prev_pos2)
        else:
            # List
            items = [first]
            if self.current_token.type is TokenType.comma:
                self.eat()
                while self.current_token.type is not TokenType.rbrace:
                    items.append(self.expr())
                    if self.current_token.type is TokenType.comma:
                        self.eat()
                    else:
                        break
            self.eat(TokenType.rbrace)
            return ast.ListDef(items, begin=pos1, end=self.prev_pos2)

    def expr_l0(self) -> ast.Expression:
        """
        expr_l0 := (LPAREN expr RPAREN)
            | IDENTIFIER
            | INTEGER
            | TRUE
            | FALSE
            | FLOAT
            | NONE
            | SELF
            | str_literal
            | list
            | map
        """
        pos1 = self.current_pos1
        if self.current_token.type is TokenType.integer:
            value = self.current_token.value
            self.eat()
            return ast.IntLiteral(value, begin=pos1, end=self.prev_pos2)
        elif self.current_token.type in (TokenType.true, TokenType.false):
            value = self.current_token.type is TokenType.true
            self.eat()
            return ast.BoolLiteral(value, begin=pos1, end=self.prev_pos2)
        elif self.current_token.type is TokenType.none:
            self.eat()
            return ast.NoneLiteral(begin=pos1, end=self.prev_pos2)
        elif self.current_token.type is TokenType.float:
            value = self.current_token.value
            self.eat()
            return ast.FloatLiteral(value, begin=pos1, end=self.prev_pos2)
        elif self.current_token.type is TokenType.identifier:
            value = self.current_token.value
            self.eat()
            return ast.Identifier(value, begin=pos1, end=self.prev_pos2)
        elif self.current_token.type is TokenType.string_begin:
            return self.str_literal()
        elif self.current_token.type is TokenType.lparen:
            self.eat()  # eat LPAREN
            node = self.expr()
            self.eat(TokenType.rparen)
            return node
        elif self.current_token.type is TokenType.self:
            self.eat()
            return ast.Self(begin=pos1, end=self.prev_pos2)
        elif self.current_token.type is TokenType.lbrace:
            return self.list_or_map()
        else:
            self.unexpected_token()
            assert False

    def expr_l1(self) -> ast.Expression:
        """
        expr_l1 := expr_l0 (
            (POINT IDENTIFIER)
            | call_table
            | paren_list_of{LBRACKET, expr, RBRACKET}
        )*
        """
        pos1 = self.current_pos1
        node = self.expr_l0()
        while True:
            if self.current_token.type is TokenType.point:
                self.peek()
                assert self.next_token
                if self.next_token.type is TokenType.new:
                    # If we find `new` then stop parsing the expression;
                    # `statement` is responsible for parsing that
                    break
                self.eat(TokenType.point)
                attr = self.current_token.value
                self.eat(TokenType.identifier)
                node = ast.Attribute(
                    node, attr, begin=pos1, end=self.prev_pos2
                )
            elif self.current_token.type is TokenType.lparen:
                table = self.call_table()
                node = ast.Call(node, table, begin=pos1, end=self.prev_pos2)
            elif self.current_token.type is TokenType.lbracket:
                subscripts = []
                self.paren_list_of(
                    lambda: subscripts.append(self.expr()),
                    lparen=TokenType.lbracket
                )
                node = ast.Subscript(
                    node, subscripts, begin=pos1, end=self.prev_pos2
                )
            else:
                break
        return node

    def expr_l2(self) -> ast.Expression:
        """expr_l2 := (PLUS | MINUS)* expr_l1"""
        ops: List[ast.UnaryOperator] = []
        while self.current_token.type in UNARY_OP_TOKENS:
            op_cls = UNARY_OP_TOKENS[self.current_token.type]
            ops.append(op_cls(*self.current_range))
            self.eat()
        ops.reverse()
        node = self.expr_l1()
        pos2 = node.end
        for op in ops:
            node = ast.UnaryOp(op, node, begin=op.begin, end=pos2)
        return node

    def expr_l3(self) -> ast.Expression:
        """expr_l3 := expr_l2 ((STAR | SLASH | MOD) expr_l2)*"""
        node = self.expr_l2()
        pos1 = node.begin
        while self.current_token.type in BIN_OP_TOKENS1:
            op_cls = BIN_OP_TOKENS1[self.current_token.type]
            op = op_cls(*self.current_range)
            self.eat()  # eat operator
            operand = self.expr_l2()
            node = ast.BinOp(node, op, operand, begin=pos1, end=self.prev_pos2)
        return node

    def expr_l4(self) -> ast.Expression:
        """expr_l4 := expr_l3 ((PLUS | MINUS) expr_l3)*"""
        node = self.expr_l3()
        pos1 = node.begin
        while self.current_token.type in BIN_OP_TOKENS2:
            op_cls = BIN_OP_TOKENS2[self.current_token.type]
            op = op_cls(*self.current_range)
            self.eat()  # eat operator
            operand = self.expr_l3()
            node = ast.BinOp(node, op, operand, begin=pos1, end=self.prev_pos2)
        return node

    def expr_l5(self) -> ast.Expression:
        """
        expr_l5 := expr_l4 ((EQUAL_TO | UNEQUAL_TO | GREATER | LESS
            | GREATER_EQUAL | LESS_EQUAL) expr_l4)*
        """
        pos1 = self.current_pos1
        left = self.expr_l4()
        operands, operators = [], []
        while self.current_token.type in COMPARE_OP_TOKENS:
            op_cls = COMPARE_OP_TOKENS[self.current_token.type]
            operators.append(op_cls(*self.current_range))
            self.eat()
            operands.append(self.expr_l4())
        if operators:
            return ast.CompareOp(
                left, operators, operands,
                begin=pos1, end=self.prev_pos2
            )
        return left

    def expr_l6(self) -> ast.Expression:
        """expr_l6 := NOT* expr_l5"""
        ops: List[ast.UnaryNot] = []
        while self.current_token.type is TokenType.not_:
            ops.append(ast.UnaryNot(*self.current_range))
            self.eat()
        ops.reverse()
        node = self.expr_l5()
        pos2 = node.end
        for op in ops:
            node = ast.UnaryOp(op, node, begin=op.begin, end=pos2)
        return node

    def expr_l7(self) -> ast.Expression:
        """expr_l7 := expr_l6 (AND expr_l6)*"""
        pos1 = self.current_pos1
        left = self.expr_l6()
        operands = []
        while self.current_token.type is TokenType.and_:
            self.eat()  # eat AND
            operands.append(self.expr_l6())
        if operands:
            operands.insert(0, left)
            return ast.BoolOp(
                ast.And(), operands, begin=pos1, end=self.prev_pos2
            )
        return left

    def expr_l8(self) -> ast.Expression:
        """expr_l8 := expr_l7 (OR expr_l7)*"""
        pos1 = self.current_pos1
        left = self.expr_l7()
        operands = []
        while self.current_token.type is TokenType.or_:
            self.eat()  # eat OR
            operands.append(self.expr_l7())
        if operands:
            operands.insert(0, left)
            return ast.BoolOp(
                ast.Or(), operands, begin=pos1, end=self.prev_pos2
            )
        return left

    # Toplevel entry to parse an expression; always set to the highest
    # level of expression parsing method:
    expr = expr_l8

    ## Statement generator

    def _id_def(self) -> ast.IdentifierDef:
        """Simply eats an IDENTIFIER and returns it as an `IdentifierDef`."""
        name = self.current_token.value
        id_range = self.current_range
        self.eat(TokenType.identifier)
        return ast.IdentifierDef(name, *id_range)

    def if_stmt(self):
        """
        if_stmt := IF expr COLON statement_block
            (ELIF expr COLON statement_block)*
            (ELSE COLON statement_block)?
        """
        # Parsing...
        if_pos1 = self.current_pos1
        self.eat(TokenType.if_)
        condition = self.expr()
        self.eat(TokenType.colon)
        stmts = self.statement_block()
        elifs = []
        while self.current_token.type is TokenType.elif_:
            elif_pos = self.current_pos1
            self.eat()  # eat ELIF
            elif_condition = self.expr()
            self.eat(TokenType.colon)
            elif_stmts = self.statement_block()
            elifs.append((elif_pos, elif_condition, elif_stmts))
        else_stmts: List[ast.Statement] = []
        if self.current_token.type is TokenType.else_:
            self.eat()  # eat ELSE
            self.eat(TokenType.colon)
            else_stmts = self.statement_block()
        # Work out what the last statement block is to know ending
        # location
        if else_stmts:
            last_block = else_stmts
        elif elifs:
            _, _, last_block = elifs[-1]
        else:
            last_block = stmts
        pos2 = last_block[-1].end
        # Assembling AST...
        elifs.reverse()
        for elif_pos, elif_condition, elif_stmts in elifs:
            else_stmts = [ast.If(
                elif_condition, elif_stmts, else_stmts,
                begin=elif_pos, end=pos2
            )]
        return ast.If(condition, stmts, else_stmts, begin=if_pos1, end=pos2)

    def while_stmt(self):
        """while_stmt := WHILE expr COLON statement_block"""
        pos1 = self.current_pos1
        self.eat(TokenType.while_)
        condition = self.expr()
        self.eat(TokenType.colon)
        body = self.statement_block()
        return ast.While(condition, body, begin=pos1, end=body[-1].end)

    def pass_stmt(self):
        """pass_stmt := PASS"""
        node = ast.Pass(*self.current_range)
        self.eat(TokenType.pass_)
        return node

    def interface_stmt(self):
        """
        interface_stmt := INTERFACE (INTERFACE_PATH | str_literal)
            COLON statement_block
        """
        pos1 = self.current_pos1
        self.eat(TokenType.interface)
        if self.current_token.type is TokenType.interface_path:
            path = ast.SimpleInterfacePath(
                self.current_token.value, *self.current_range
            )
            self.eat()
        else:
            path = self.str_literal()
        self.eat(TokenType.colon)
        self.scopes.append(Scope.INTERFACE)
        stmts = self.statement_block()
        self.scopes.pop()
        return ast.InterfaceDef(path, stmts, begin=pos1, end=stmts[-1].end)

    def _valpassing_qualifier(self, func_type: FuncType) -> ast.ValuePassing:
        """valpassing_inline := (CONST | AMPERSAND)?"""
        pos1 = self.current_pos1
        if self.current_token.type is TokenType.const:
            self.eat()
            res = ast.PassConst
        elif self.current_token.type is TokenType.ampersand:
            self.eat()
            res = ast.PassByReference
        else:
            res = ast.PassByValue
        pos2 = pos1 if res is ast.PassByValue else self.prev_pos2
        if res not in func_type.allowed_valpassing:
            self.error_range(
                'invalid-valpassing', pos1, pos2,
                args={'qualifier': STStr(res.display_name),
                      'func-type': STEnum(func_type.qualifier)}
            )
        return res(pos1, pos2)

    def _def_head(self) -> ast.IdentifierDef:
        """def_head := DEF IDENTIFIER"""
        self.eat(TokenType.def_)
        return self._id_def()

    def _function_def(self, func_type: FuncType) -> ast.FuncData:
        arg_table = self.argument_table(func_type)
        if self.current_token.type is TokenType.arrow:
            self.eat()
            qualifier = self._valpassing_qualifier(func_type)
            ret_type = self.type_spec()
            returns = ast.ReturnSpec(ret_type, qualifier)
        else:
            returns = None
        self.eat(TokenType.colon)
        self.scopes.append(Scope.FUNCTION)
        stmts = self.statement_block()
        self.scopes.pop()
        return ast.FuncData(func_type.qualifier, arg_table, stmts, returns)

    def const_def_stmt(self):
        """
        funcdef_const := argtable_const (ARROW type_spec)?
            COLON statement_block
        const_def_stmt := CONST def_head fundef_const
        """
        pos1 = self.current_pos1
        self.eat(TokenType.const)
        name = self._def_head()
        func_data = self._function_def(FUNC_CONST)
        return ast.FuncDef(
            name, func_data, begin=pos1, end=func_data.body[-1].end
        )

    def inline_def_stmt(self):
        """
        funcdef_inline := argtable_inline
            (ARROW valpassing_inline type_spec)?
            COLON statement_block
        inline_def_stmt := INLINE def_head funcdef_inline
        """
        pos1 = self.current_pos1
        self.eat(TokenType.inline)
        name = self._def_head()
        func_data = self._function_def(FUNC_INLINE)
        return ast.FuncDef(
            name, func_data, begin=pos1, end=func_data.body[-1].end
        )

    def def_stmt(self):
        """
        funcdef_normal := argtable_normal (ARROW type_spec)?
            COLON statement_block
        def_stmt := def_head funcdef_normal
        """
        pos1 = self.current_pos1
        name = self._def_head()
        func_data = self._function_def(FUNC_NORMAL)
        return ast.FuncDef(
            name, func_data, begin=pos1, end=func_data.body[-1].end
        )

    def _entity_body(self):
        pos1 = self.current_pos1
        if self.current_token.type is TokenType.identifier:
            # entity_field_decl
            id_def = self._id_def()
            self.eat(TokenType.colon)
            type_ = self.type_spec()
            pos2 = self.prev_pos2
            self.eat(TokenType.new_line)
            return ast.EntityField(id_def, type_, begin=pos1, end=pos2)
        elif self.current_token.type is TokenType.pass_:
            res = self.pass_stmt()
            self.eat(TokenType.new_line)
            return res
        else:
            # method_decl or new_method_decl
            # Check if it is new method...
            if self.current_token.type is TokenType.const:
                self.peek()
                assert self.next_token
                if self.next_token.type is TokenType.new:
                    self.error_range(
                        'const-new-method', pos1=pos1,
                        pos2=self.next_token.pos2
                    )
            if self.current_token.type is TokenType.inline:
                self.peek()
                assert self.next_token
                tok = self.next_token
            else:
                tok = self.current_token
            if tok.type is TokenType.new:
                if self.current_token.type is TokenType.inline:
                    self.eat()
                    t = FUNC_INLINE
                else:
                    t = FUNC_NORMAL
                new_range = self.current_range
                self.eat(TokenType.new)
                data = self._function_def(t)
                return ast.NewMethod(
                    data, *new_range, begin=pos1, end=data.body[-1].end
                )
            # It is not new method, normal method then...
            qualifier = ast.MethodQualifier.none
            if self.current_token.type is TokenType.virtual:
                self.eat()  # eat "virtual"
                qualifier = ast.MethodQualifier.virtual
            elif self.current_token.type is TokenType.override:
                self.eat()  # eat "override"
                qualifier = ast.MethodQualifier.override
            elif self.current_token.type is TokenType.static:
                self.eat()  # eat "static"
                qualifier = ast.MethodQualifier.static
            if self.current_token.type is TokenType.inline:
                content = self.inline_def_stmt()
            elif self.current_token.type is TokenType.const:
                content = self.const_def_stmt()
                if qualifier is not ast.MethodQualifier.static:
                    self.error_range(
                        'non-static-const-method',
                        *content.name.source_range
                    )
            else:
                content = self.def_stmt()
            return ast.EntityMethod(
                content, qualifier, begin=pos1, end=self.prev_pos2
            )

    def _extends_clause(self) -> List[ast.Expression]:
        """extends_clause := (EXTENDS list_of{expr})?"""
        bases = []
        if self.current_token.type is TokenType.extends:
            self.eat()
            self.list_of(lambda: bases.append(self.expr()))
        return bases

    def entity_stmt(self):
        """
        entity_stmt := ENTITY IDENTIFIER extends_clause
            COLON block_of{entity_body}
        entity_field_decl := IDENTIFIER COLON type_spec
        method_decl := (
            (VIRTUAL | OVERRIDE | STATIC)? (def_stmt | inline_def_stmt)
            | (STATIC const_def_stmt)
        )
        new_method_decl := (NEW funcdef_normal)
            | (INLINE NEW funcdef_inline)
        entity_body := (method_decl | new_method_decl)
            | ((entity_field_decl | pass_stmt) NEW_LINE)
        """
        # Header
        pos1 = self.current_pos1
        self.eat(TokenType.entity)
        id_def = self._id_def()
        parents = self._extends_clause()
        self.eat(TokenType.colon)
        # Body
        new_method: Optional[ast.NewMethod] = None
        methods: Dict[str, ast.EntityMethod] = {}
        fields: Dict[str, ast.EntityField] = {}
        last_pos2: Optional[LineCol] = None
        def duplication_check(item_name: ast.IdentifierDef):
            # This is shared by methods and fields
            name = item_name.name
            if name in fields:
                prev_name = fields[name].name
            elif name in methods:
                prev_name = methods[name].content.name
            else:
                return
            # Error: this name has already been defined
            err = DiagnosticError(self.diag_obj(
                'duplicate-entity-attr',
                *item_name.source_range,
                {"name": STStr(name)}
            ))
            err.add_note(self.diag_obj(
                'duplicate-entity-attr-note',
                *prev_name.source_range
            ))
            raise err
        for _ in self.indented_block():
            item = self._entity_body()
            last_pos2 = item.end
            if isinstance(item, ast.Pass):
                continue
            if isinstance(item, ast.NewMethod):
                if new_method is None:
                    new_method = item
                    continue
                # Error: multiple new methods
                err = DiagnosticError(self.diag_obj(
                    'multiple-new-methods',
                    item.new_begin, item.new_end
                ))
                err.add_note(self.diag_obj(
                    'multiple-new-methods-note',
                    new_method.new_begin, new_method.new_end
                ))
                raise err
            if isinstance(item, ast.EntityField):
                duplication_check(item.name)
                fields[item.name.name] = item
            else:
                assert isinstance(item, ast.EntityMethod)
                duplication_check(item.content.name)
                methods[item.content.name.name] = item
        assert last_pos2 is not None
        return ast.EntityTemplateDef(
            id_def, parents,
            list(fields.values()), list(methods.values()),
            new_method,
            begin=pos1, end=last_pos2
        )

    def formatted_str(self):
        """formatted_str := (STRING_BODY | (DOLLAR_LBRACE expr RBRACE))*"""
        res = []
        while self.current_token.type in (
            TokenType.text_body, TokenType.dollar_lbrace
        ):
            if self.current_token.type is TokenType.text_body:
                res.append(self.current_token.value)
                self.eat()
            else:
                self.eat(TokenType.dollar_lbrace)
                res.append(self.expr())
                self.eat(TokenType.rbrace)
        return ast.FormattedStr(res)

    def command_stmt(self):
        """command_stmt := COMMAND_BEGIN formatted_str COMMAND_END"""
        pos1 = self.current_pos1
        self.eat(TokenType.command_begin)
        content = self.formatted_str()
        self.eat(TokenType.command_end)
        return ast.Command(content, begin=pos1, end=self.prev_pos2)

    def module_meta(self) -> Tuple[ast.ModuleMeta, LineColRange]:
        """module_meta := IDENTIFIER (POINT IDENTIFIER)*"""
        # at least one name should be given
        pos1 = self.current_pos1
        names = [self.current_token.value]
        last_range = self.current_range
        self.eat(TokenType.identifier)
        # read more names
        while self.current_token.type is TokenType.point:
            self.eat()
            names.append(self.current_token.value)
            last_range = self.current_range
            self.eat(TokenType.identifier)
        meta = ast.ModuleMeta(names, begin=pos1, end=self.prev_pos2)
        return meta, last_range

    def alias(self) -> Optional[ast.IdentifierDef]:
        """alias := (AS IDENTIFIER)?"""
        if self.current_token.type is TokenType.as_:
            self.eat()
            return self._id_def()
        return None

    def import_stmt(self):
        """import_stmt := IMPORT module_meta alias"""
        pos1 = self.current_pos1
        self.eat(TokenType.import_)
        meta, last_range = self.module_meta()
        alias = self.alias()
        if alias is None:
            alias = ast.IdentifierDef(meta.path[-1], *last_range)
        return ast.Import(meta, alias, begin=pos1, end=self.prev_pos2)

    def from_import_stmt(self):
        """
        id_alias := IDENTIFIER alias
        from_import_stmt := FROM module_meta IMPORT (
            STAR
            | list_of{id_alias}
            | paren_list_of{LPAREN, id_alias, RPAREN}
        )
        """
        pos1 = self.current_pos1
        self.eat(TokenType.from_)
        meta, _ = self.module_meta()
        self.eat(TokenType.import_)
        if self.current_token.type is TokenType.star:
            star_range = self.current_range
            self.eat()
            return ast.FromImportAll(
                meta, *star_range, begin=pos1, end=self.prev_pos2
            )
        items: List[ast.ImportItem] = []
        def _id_alias():
            name = self._id_def()
            alias = self.alias()
            if alias is None:
                alias = ast.IdentifierDef(name.name, *name.source_range)
            items.append(ast.ImportItem(name, alias))
        if self.current_token.type is TokenType.lparen:
            self.paren_list_of(_id_alias)
        else:
            self.list_of(_id_alias)
        return ast.FromImport(meta, items, begin=pos1, end=self.prev_pos2)

    def for_stmt(self):
        """
        for_stmt := FOR IDENTIFIER IN expr COLON statement_block
        """
        pos1 = self.current_pos1
        self.eat(TokenType.for_)
        id_def = self._id_def()
        self.eat(TokenType.in_)
        expr = self.expr()
        self.eat(TokenType.colon)
        body = self.statement_block()
        return ast.For(id_def, expr, body, begin=pos1, end=body[-1].end)

    def _struct_body(self):
        pos1 = self.current_pos1
        if self.current_token.type is TokenType.identifier:
            id_def = self._id_def()
            self.eat(TokenType.colon)
            type_ = self.type_spec()
            res = ast.StructField(
                id_def, type_, begin=pos1, end=self.prev_pos2
            )
        else:
            res = self.pass_stmt()
        self.eat(TokenType.new_line)
        return res

    def struct_stmt(self):
        """
        struct_field_decl := IDENTIFIER COLON type_spec
        struct_body := ((struct_field_decl | pass_stmt) NEW_LINE)*
        struct_stmt := STRUCT IDENTIFIER extends_clause
            COLON block_of{struct_body}
        """
        pos1 = self.current_pos1
        self.eat(TokenType.struct)
        id_def = self._id_def()
        bases = self._extends_clause()
        self.eat(TokenType.colon)
        last_pos2: Optional[LineCol] = None
        fields: Dict[str, ast.StructField] = {}
        for _ in self.indented_block():
            item = self._struct_body()
            last_pos2 = item.end
            if isinstance(item, ast.Pass):
                continue
            name = item.name.name
            if name not in fields:
                fields[name] = item
                continue
            # Error: multiple fields of the same name
            prev_item = fields[name]
            err = DiagnosticError(self.diag_obj(
                'duplicate-struct-attr',
                *item.name.source_range,
                {"name": STStr(name)}
            ))
            err.add_note(self.diag_obj(
                'duplicate-struct-attr-note',
                *prev_item.name.source_range
            ))
            raise err
        assert last_pos2 is not None
        return ast.StructDef(
            id_def, bases, list(fields.values()), begin=pos1, end=last_pos2
        )

    def _constant_decl(self) -> ast.CompileTimeAssign:
        """constant_decl := IDENTIFIER (COLON type_spec)? EQUAL expr"""
        id_def = self._id_def()
        if self.current_token.type is TokenType.colon:
            self.eat()
            type_ = self.type_spec()
        else:
            type_ = None
        self.eat(TokenType.equal)
        value = self.expr()
        return ast.CompileTimeAssign(id_def, type_, value)

    def _handle_const(self):
        """
        constant_def_body := list_of{constant_decl}
            | paren_list_of{LPAREN, constant_decl, RPAREN}
        const_statement := const_def_stmt
            | (CONST constant_def_body NEW_LINE)
        """
        self.peek()
        assert self.next_token
        if self.next_token.type is TokenType.def_:
            return self.const_def_stmt()
        pos1 = self.current_pos1
        self.eat()  # eat CONST
        contents = []
        def _add_const_decl():
            contents.append(self._constant_decl())
        if self.current_token.type is TokenType.lparen:
            self.paren_list_of(_add_const_decl)
        else:
            self.list_of(_add_const_decl)
        pos2 = self.prev_pos2
        self.eat(TokenType.new_line)
        return ast.ConstDef(contents, begin=pos1, end=pos2)

    def reference_def_stmt(self):
        """reference_def_stmt := AMPERSAND constant_decl"""
        pos1 = self.current_pos1
        self.eat(TokenType.ampersand)
        decl = self._constant_decl()
        return ast.ReferenceDef(decl, begin=pos1, end=self.prev_pos2)

    def return_stmt(self):
        """return_stmt := RETURN expr?"""
        pos1 = self.current_pos1
        self.eat(TokenType.return_)
        # Check if this "return" is inside function or interface
        if self.scopes[-1] not in (Scope.FUNCTION, Scope.INTERFACE):
            self.error_range("return-scope", pos1, self.prev_pos2)
        # Expects an expression iff we are not at end of line:
        if self.current_token.type is TokenType.new_line:
            expr = None
        else:
            expr = self.expr()
            if self.scopes[-1] is Scope.INTERFACE:
                self.error_range("interface-return-value", *expr.source_range)
        return ast.Return(expr, begin=pos1, end=self.prev_pos2)

    def simple_new_stmt(self):
        """simple_new_stmt := NEW call_table"""
        pos1 = self.current_pos1
        self.eat(TokenType.new)
        table = self.call_table()
        return ast.NewCall(None, table, begin=pos1, end=self.prev_pos2)

    def statement(self):
        """
        expr_statement := (
            var_def_stmt | auto_var_def_stmt | assign_stmt |
            aug_assign_stmt | expr_stmt | expr_new_stmt
        )
        simple_statement := (
            pass_stmt | command_stmt | import_stmt | from_import_stmt |
            return_stmt | simple_new_stmt
        )
        embedded_statement := (
            if_stmt | while_stmt | for_stmt | interface_stmt |
            def_stmt | entity_stmt | struct_stmt | inline_def_stmt
        )
        statement := ((simple_statement | expr_statement) NEW_LINE) |
            embedded_statement | const_statement
        """
        if self.current_token.type is TokenType.const:
            return self._handle_const()
        stmt_method = self.token_to_simple_stmt.get(self.current_token.type)
        if stmt_method:
            res = stmt_method()
            self.eat(TokenType.new_line)
            return res
        stmt_method = self.token_to_complex_stmt.get(self.current_token.type)
        if stmt_method:
            return stmt_method()

        # Other statements that start with an expression
        pos1 = self.current_pos1
        expr = self.expr()

        if self.current_token.type is TokenType.equal:
            # assign_stmt := expr EQUAL expr
            self.eat()  # eat equal
            rhs = self.expr()
            node = ast.Assign(expr, rhs, begin=pos1, end=self.prev_pos2)
        elif self.current_token.type in AUG_ASSIGN_TOKENS:
            # aug_assign_stmt := expr (PLUS_EQUAL | MINUS_EQUAL
            #     | TIMES_EQUAL | DIVIDE_EQUAL | MOD_EQUAL) expr
            operator_cls = AUG_ASSIGN_TOKENS[self.current_token.type]
            operator = operator_cls(*self.current_range)
            self.eat()  # eat operator
            rhs = self.expr()
            node = ast.AugmentedAssign(
                expr, operator, rhs, begin=pos1, end=self.prev_pos2
            )
        elif self.current_token.type is TokenType.colon:
            # var_def_stmt := IDENTIFIER COLON type_spec (EQUAL expr)?
            self.eat()  # eat colon
            if not isinstance(expr, ast.Identifier):
                self.error_range('invalid-var-def', *expr.source_range)
                assert False
            type_ = self.type_spec()
            if self.current_token.type is TokenType.equal:
                self.eat()  # eat equal
                rhs = self.expr()
            else:
                rhs = None
            node = ast.VarDef(
                ast.IdentifierDef(expr.name, *expr.source_range),
                type_, rhs, begin=pos1, end=self.prev_pos2
            )
        elif self.current_token.type is TokenType.walrus:
            # auto_var_def_stmt := IDENTIFIER WALRUS expr
            self.eat()  # eat walrus
            if not isinstance(expr, ast.Identifier):
                self.error_range('invalid-var-def', *expr.source_range)
                assert False
            id_def = ast.IdentifierDef(expr.name, *expr.source_range)
            rhs = self.expr()
            node = ast.AutoVarDef(id_def, rhs, begin=pos1, end=self.prev_pos2)
        else:  # just an expr, or a new statement
            # expr_stmt := expr
            # expr_new_stmt := expr POINT NEW call_table
            node = None
            if self.current_token.type is TokenType.point:
                self.peek()
                assert self.next_token
                if self.next_token.type is TokenType.new:
                    self.eat()
                    self.eat()
                    table = self.call_table()
                    node = ast.NewCall(
                        expr, table, begin=pos1, end=self.prev_pos2
                    )
            if node is None:
                node = ast.ExprStatement(expr)
        self.eat(TokenType.new_line)
        return node

    ## Other generators

    def module(self) -> ast.Module:
        """module := statement* END_MARKER"""
        stmts = []
        while self.current_token.type is not TokenType.end_marker:
            stmts.append(self.statement())
        return ast.Module(stmts)

    def argument_table(self, func_type: FuncType) -> List[ast.FormalParam]:
        """
        type_decl := COLON type_spec
        default_decl := EQUAL expr
        arg_normal := IDENTIFIER
            ((type_decl | default_decl) | (type_decl default_decl))
        arg_inline := valpassing_inline IDENTIFIER type_decl?
            default_decl?
        arg_const := IDENTIFIER type_decl? default_decl?
        argtable_normal := paren_list_of{LPAREN, arg_normal, RPAREN}
        argtable_inline := paren_list_of{LPAREN, arg_inline, RPAREN}
        argtable_const := paren_list_of{LPAREN, arg_const, RPAREN}
        """
        got_default = False
        params = OrderedDict()
        def _arg_decl():
            nonlocal got_default
            # read qualifier
            qualifier = self._valpassing_qualifier(func_type)
            # read name
            arg_token = self.current_token
            name = self.current_token.value
            self.eat()  # eat IDENTIFIER
            # read type
            type_ = None
            if self.current_token.type is TokenType.colon:
                self.eat()
                type_ = self.type_spec()
            # read default
            default = None
            if self.current_token.type is TokenType.equal:
                self.eat()
                default = self.expr()
                got_default = True
            elif got_default:
                self.error('non-default-arg-after-default',
                           arg_token, args={"arg": STStr(name)})
            # check
            if (not (type_ or default)) and func_type.type_required:
                self.error('dont-know-arg-type',
                           arg_token, args={"arg": STStr(name)})
            if name in params:
                self.error('duplicate-arg',
                           arg_token, args={"arg": STStr(name)})
            # add arg
            id_def = ast.IdentifierDef(name, arg_token.pos1, arg_token.pos2)
            params[name] = ast.FormalParam(id_def, qualifier, type_, default)
        self.paren_list_of(_arg_decl)
        return list(params.values())

    def type_spec(self) -> ast.TypeSpec:
        """type_spec := expr"""
        return ast.TypeSpec(self.expr())

    def call_table(self) -> ast.CallTable:
        """
        arg := (IDENTIFIER EQUAL)? expr
        call_table := paren_list_of{LPAREN, arg, RPAREN}
        # Note this grammar does not show the fact that all keyword
        # arguments must be placed after positional arguments.
        """
        args, keywords = [], {}
        got_keyword = False  # if a keyword argument has been read
        def _arg():
            nonlocal got_keyword
            self.peek()
            assert self.next_token
            if self.next_token.type is TokenType.equal:
                # keyword
                got_keyword = True
                key = self.current_token.value
                keyword_token = self.current_token
                self.eat(TokenType.identifier)
                if key in keywords:  # if already exists
                    self.error(
                        'duplicate-keyword-args', keyword_token,
                        args={'arg': STStr(key)}
                    )
                self.eat(TokenType.equal)
                keywords[key] = self.expr()
            else:  # positioned
                expr = self.expr()
                if got_keyword:
                    self.error_range(
                        'positional-arg-after-keyword',
                        *expr.source_range
                    )
                args.append(expr)
        pos1 = self.current_pos1
        self.paren_list_of(_arg)
        return ast.CallTable(args, keywords, pos1, self.prev_pos2)
