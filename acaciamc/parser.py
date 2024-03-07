"""Parser for Acacia."""

__all__ = ['Parser']

from typing import Callable, Optional, List, Tuple, TYPE_CHECKING

from acaciamc.error import *
from acaciamc.tokenizer import TokenType, BRACKETS
from acaciamc.ast import *

if TYPE_CHECKING:
    from acaciamc.tokenizer import Tokenizer

NORMAL_FUNC_PORTS = CONST_FUNC_PORTS = (FuncPortType.by_value,)
INLINE_FUNC_PORTS = (FuncPortType.by_value, FuncPortType.by_reference,
                     FuncPortType.const)

class Parser:
    def __init__(self, tokenizer: "Tokenizer"):
        self.tokenizer = tokenizer
        self.current_token = self.tokenizer.get_next_token()
        self.next_token = None

    @property
    def current_pos(self):
        return {
            "lineno": self.current_token.lineno,
            "col": self.current_token.col
        }

    def error(self, err_type: ErrorType, lineno=None, col=None, **kwargs):
        if lineno is None:
            lineno = self.current_pos['lineno']
        if col is None:
            col = self.current_pos['col']
        err = Error(err_type, **kwargs)
        err.location.linecol = (lineno, col)
        raise err

    def eat(self, expect_token_type: Optional[TokenType] = None):
        """Move to next token.
        If `expect_token_type` is given, also check type of the old
        token.
        """
        if ((expect_token_type is not None) and
            (self.current_token.type != expect_token_type)):
            self.error(ErrorType.UNEXPECTED_TOKEN, token=self.current_token)
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

    def _block(self, func: Callable[[], Statement]):
        """
        Read an indented block of structures.
        `func` reads the structure and should return the result AST.
        block{n} := NEW_LINE INDENT n+ DEDENT
        """
        stmts = []
        self.eat(TokenType.new_line)
        if self.current_token.type is not TokenType.indent:
            self.error(ErrorType.EMPTY_BLOCK)
        self.eat()  # INDENT
        while self.current_token.type != TokenType.dedent:
            stmts.append(func())
        self.eat()  # DEDENT
        return stmts

    def statement_block(self):
        """
        Read a block of statements.
        statement_block := block{statement}
        """
        return self._block(self.statement)

    # Following are different AST generators
    ## Expression generator

    def literal(self):
        """literal := INTEGER | TRUE | FALSE | NONE | FLOAT"""
        pos = self.current_pos
        tok_type = self.current_token.type
        if tok_type in (TokenType.integer, TokenType.float_):
            value = self.current_token.value
            self.eat()
        elif tok_type in (TokenType.true, TokenType.false):
            value = tok_type is TokenType.true
            self.eat()
        elif tok_type is TokenType.none:
            value = None
            self.eat()
        else:
            self.error(ErrorType.UNEXPECTED_TOKEN, token=self.current_token)
        return Literal(value, **pos)

    def str_literal(self):
        """str_literal := (STRING_BEGIN formatted_str STRING_END)+"""
        pos = self.current_pos
        content: List[str] = []
        while self.current_token.type is TokenType.string_begin:
            self.eat()  # eat STRING_BEGIN
            content.extend(self.formatted_str().content)
            self.eat(TokenType.string_end)
        return StrLiteral(FormattedStr(content, **pos), **pos)

    def identifier(self):
        """identifier := IDENTIFIER"""
        pos = self.current_pos
        token = self.current_token
        self.eat(TokenType.identifier)
        return Identifier(token.value, **pos)

    def self(self):
        """self := SELF"""
        pos = self.current_pos
        self.eat(TokenType.self)
        return Self(**pos)

    def list_or_map(self):
        """
        list := paren_list_of{LBRACE, expr, RBRACE}
        map_item := expr COLON expr
        map := LBRACE ((map_item (COMMA map_item)* COMMA?) | COLON)
          RBRACE
        """
        pos = self.current_pos
        self.eat(TokenType.lbrace)
        # Check for empty list or map
        if self.current_token.type is TokenType.rbrace:
            self.eat()
            return ListDef(items=[], **pos)
        elif self.current_token.type is TokenType.colon:
            self.eat()
            self.eat(TokenType.rbrace)
            return MapDef(keys=[], values=[], **pos)
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
            return MapDef(keys, values, **pos)
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
            return ListDef(items, **pos)

    def expr_l0(self):
        """
        level 0 expression := (LPAREN expr RPAREN) | literal
          | identifier | str_literal | self | list | map
        """
        if self.current_token.type in (
            TokenType.integer, TokenType.float_, TokenType.true,
            TokenType.false, TokenType.none
        ):
            return self.literal()
        elif self.current_token.type is TokenType.identifier:
            return self.identifier()
        elif self.current_token.type is TokenType.string_begin:
            return self.str_literal()
        elif self.current_token.type is TokenType.lparen:
            self.eat(TokenType.lparen)
            node = self.expr()
            self.eat(TokenType.rparen)
            return node
        elif self.current_token.type is TokenType.self:
            return self.self()
        elif self.current_token.type is TokenType.lbrace:
            return self.list_or_map()
        else:
            self.error(ErrorType.UNEXPECTED_TOKEN, token=self.current_token)

    def expr_l1(self):
        """
        level 1 expression := expr_l0 (
          (POINT IDENTIFIER)
          | call_table
          | paren_list_of{LBRACKET, expr, RBRACKET}
          | (AT expr_l0)
        )*
        """
        node = self.expr_l0()
        def _attribute(node: Expression):
            # make `node` an Attribute
            self.eat(TokenType.point)
            attr = self.current_token.value
            self.eat(TokenType.identifier)
            return Attribute(node, attr, lineno=node.lineno, col=node.col)

        def _call(node: Expression):
            return Call(
                node, self.call_table(),
                lineno=node.lineno, col=node.col
            )

        def _subscript(node: Expression):
            subscripts = []
            self.paren_list_of(
                lambda: subscripts.append(self.expr()),
                lparen=TokenType.lbracket
            )
            return Subscript(
                node, subscripts, lineno=node.lineno, col=node.col
            )

        def _entity_cast(node: Expression):
            self.eat(TokenType.at)
            object_ = self.expr_l0()
            return EntityCast(object_, template=node,
                              lineno=node.lineno, col=node.col)

        # start
        while True:
            if self.current_token.type is TokenType.point:
                node = _attribute(node)
            elif self.current_token.type is TokenType.lparen:
                node = _call(node)
            elif self.current_token.type is TokenType.lbracket:
                node = _subscript(node)
            elif self.current_token.type is TokenType.at:
                node = _entity_cast(node)
            else:
                return node

    def expr_l2(self):
        """level 2 expression := ((PLUS | MINUS) expr_l2) | expr_l1"""
        pos = self.current_pos
        if self.current_token.type is TokenType.plus:
            self.eat()
            return UnaryOp(Operator.positive, self.expr_l2(), **pos)
        elif self.current_token.type is TokenType.minus:
            self.eat()
            return UnaryOp(Operator.negative, self.expr_l2(), **pos)
        else:  # no unary operators
            return self.expr_l1()

    def expr_l3(self):
        """level 3 expression := expr_l2 ((STAR | SLASH | MOD) expr_l2)*"""
        node = self.expr_l2()
        while True:
            token_type = self.current_token.type
            if token_type is TokenType.star:
                op = Operator.multiply
            elif token_type is TokenType.slash:
                op = Operator.divide
            elif token_type is TokenType.mod:
                op = Operator.mod
            else:  # no valid operator found
                return node
            self.eat()  # eat operator
            node = BinOp(
                node, op, self.expr_l2(),
                lineno=node.lineno, col=node.col
            )

    def expr_l4(self):
        """level 4 expression := expr_l3 ((ADD | MINUS) expr_l3)*"""
        node = self.expr_l3()
        while True:
            token_type = self.current_token.type
            if token_type is TokenType.plus:
                op = Operator.add
            elif token_type is TokenType.minus:
                op = Operator.minus
            else:  # no valid operator found
                return node
            self.eat()  # eat operator
            node = BinOp(node, op, self.expr_l3(),
                         lineno=node.lineno, col=node.col)

    def expr_l5(self):
        """
        level 5 expression := expr_l4 ((
          EQUAL_TO | UNEQUAL_TO | GREATER | LESS | GREATER_EQUAL | LESS_EQUAL
        ) expr_l4)*
        """
        pos = self.current_pos
        left = self.expr_l4()
        COMPARE_OPS = (
            TokenType.equal_to,
            TokenType.unequal_to,
            TokenType.greater,
            TokenType.less,
            TokenType.greater_equal,
            TokenType.less_equal
        )
        operands, operators = [], []
        while self.current_token.type in COMPARE_OPS:
            operators.append(Operator[self.current_token.type.name])
            self.eat()
            operands.append(self.expr_l4())
        if operators:  # if not empty
            return CompareOp(left, operators, operands, **pos)
        return left

    def expr_l6(self):
        """level 6 expression := (NOT expr_l6) | expr_l5"""
        pos = self.current_pos
        if self.current_token.type is TokenType.not_:
            self.eat()
            return UnaryOp(Operator.not_, self.expr_l6(), **pos)
        else:  # no unary operators
            return self.expr_l5()

    def expr_l7(self):
        """level 7 expression := expr_l6 (AND expr_l6)*"""
        left = self.expr_l6()
        operands = []
        while self.current_token.type is TokenType.and_:
            self.eat()  # eat and_
            operands.append(self.expr_l6())
        if operands:  # if not empty
            operands.insert(0, left)
            return BoolOp(Operator.and_, operands,
                          lineno=left.lineno, col=left.col)
        return left

    def expr_l8(self):
        """level 8 expression := expr_l7 (OR expr_l7)*"""
        left = self.expr_l7()
        operands = []
        while self.current_token.type is TokenType.or_:
            self.eat()  # eat or_
            operands.append(self.expr_l7())
        if operands:  # if not empty
            operands.insert(0, left)
            return BoolOp(Operator.or_, operands,
                          lineno=left.lineno, col=left.col)
        return left

    # expr: keep updates with the highest level of expr method
    # this is to make sure other funcs always call the
    # highest level of expr (convenient when updating)
    expr = expr_l8

    ## Statement generator

    def if_stmt(self):
        """
        if_stmt := IF expr COLON statement_block
          (ELIF expr COLON statement_block)*
          (ELSE COLON statement_block)?
        """
        pos = self.current_pos
        def _if_extra():
            """
            if_extra := (ELIF expr COLON statement_block if_extra?)
              | (ELSE COLON statement_block)
            return list of statements
            """
            if self.current_token.type is TokenType.else_:
                self.eat()
                self.eat(TokenType.colon)
                return self.statement_block()
            elif self.current_token.type is TokenType.elif_:
                elif_pos = self.current_pos
                self.eat()
                condition = self.expr()
                self.eat(TokenType.colon)
                stmts = self.statement_block()
                # See if there are more "elif" or "else"
                else_stmts = _if_extra()
                return [If(condition, stmts, else_stmts, **elif_pos)]
            else:
                return []
        # if_stmt := IF expr COLON statement_block if_extra?
        self.eat(TokenType.if_)
        condition = self.expr()
        self.eat(TokenType.colon)
        stmts = self.statement_block()
        else_stmts = _if_extra()
        return If(condition, stmts, else_stmts, **pos)

    def while_stmt(self):
        """while_stmt := WHILE expr COLON statement_block"""
        pos = self.current_pos
        self.eat(TokenType.while_)
        condition = self.expr()
        self.eat(TokenType.colon)
        body = self.statement_block()
        return While(condition, body, **pos)

    def pass_stmt(self):
        """pass_stmt := PASS"""
        node = Pass(**self.current_pos)
        self.eat(TokenType.pass_)
        return node

    def interface_stmt(self):
        """
        interface_stmt := INTERFACE IDENTIFIER (POINT IDENTIFIER)*
          COLON statement_block
        """
        pos = self.current_pos
        self.eat(TokenType.interface)
        path = [self.current_token.value]
        self.eat(TokenType.identifier)
        while self.current_token.type is TokenType.point:
            self.eat()
            path.append(self.current_token.value)
            self.eat(TokenType.identifier)
        self.eat(TokenType.colon)
        stmts = self.statement_block()
        return InterfaceDef(path, stmts, **pos)

    def _func_port_qualifier(self, allowed_ports: Tuple[FuncPortType]) \
            -> FuncPortType:
        """func_port_qualifier := (CONST | AMPERSAND)?"""
        pos = self.current_pos
        if self.current_token.type is TokenType.const:
            self.eat()
            res = FuncPortType.const
        elif self.current_token.type is TokenType.ampersand:
            self.eat()
            res = FuncPortType.by_reference
        else:
            res = FuncPortType.by_value
        if res not in allowed_ports:
            self.error(ErrorType.INVALID_FUNC_PORT, **pos, port=res.value)
        return res

    def _function_def(self, allowed_ports: Tuple[FuncPortType],
                      type_required: bool):
        """
        function_def := DEF IDENTIFIER argument_table
          (ARROW func_port_qualifier type_spec)? COLON statement_block
        """
        self.eat(TokenType.def_)
        name = self.current_token.value
        self.eat(TokenType.identifier)
        arg_table = self.argument_table(allowed_ports, type_required)
        if self.current_token.type is TokenType.arrow:
            self.eat()
            pos = self.current_pos
            qualifier = self._func_port_qualifier(allowed_ports)
            ret_type = self.type_spec()
            returns = FunctionPort(ret_type, qualifier, **pos)
        else:
            returns = None
        self.eat(TokenType.colon)
        stmts = self.statement_block()
        return name, arg_table, stmts, returns

    def const_def_stmt(self):
        """const_def_stmt := CONST function_def"""
        pos = self.current_pos
        self.eat(TokenType.const)
        func_data = self._function_def(CONST_FUNC_PORTS, type_required=False)
        return ConstFuncDef(*func_data, **pos)

    def inline_def_stmt(self):
        """inline_def_stmt := INLINE function_def"""
        pos = self.current_pos
        self.eat(TokenType.inline)
        func_data = self._function_def(INLINE_FUNC_PORTS, type_required=False)
        return InlineFuncDef(*func_data, **pos)

    def def_stmt(self):
        """def_stmt := function_def"""
        pos = self.current_pos
        func_data = self._function_def(NORMAL_FUNC_PORTS, type_required=True)
        return FuncDef(*func_data, **pos)

    def _entity_body(self):
        pos = self.current_pos
        if self.current_token.type is TokenType.identifier:
            # entity_field_decl
            name = self.current_token.value
            self.eat()  # eat IDENTIFIER
            self.eat(TokenType.colon)
            type_ = self.type_spec()
            self.eat(TokenType.new_line)
            return EntityField(name, type_, **pos)
        elif self.current_token.type is TokenType.at:
            # meta_decl
            self.eat()  # eat "@"
            name = self.current_token.value
            self.eat(TokenType.identifier)
            self.eat(TokenType.colon)
            value = self.expr()
            self.eat(TokenType.new_line)
            return EntityMeta(name, value, **pos)
        elif self.current_token.type is TokenType.pass_:
            res = self.pass_stmt()
            self.eat(TokenType.new_line)
            return res
        else:
            # method_decl
            qualifier = MethodQualifier.none
            if self.current_token.type is TokenType.virtual:
                self.eat()  # eat "virtual"
                qualifier = MethodQualifier.virtual
            elif self.current_token.type is TokenType.override:
                self.eat()  # eat "override"
                qualifier = MethodQualifier.override
            if self.current_token.type is TokenType.inline:
                content = self.inline_def_stmt()
            else:
                content = self.def_stmt()
            return EntityMethod(content, qualifier, **pos)

    def entity_stmt(self):
        """
        entity_stmt := ENTITY IDENTIFIER (EXTENDS expr
          (COMMA expr)*)? COLON block{entity_body}
        entity_field_decl := IDENTIFIER COLON type_spec
        method_decl := (VIRTUAL | OVERRIDE)? (def_stmt | inline_def_stmt)
        meta_decl := AT IDENTIFIER COLON expr
        entity_body := method_decl | (
          (entity_field_decl | meta_decl | pass_stmt) NEW_LINE)
        """
        pos = self.current_pos
        self.eat(TokenType.entity)
        name = self.current_token.value
        self.eat(TokenType.identifier)
        parents = []
        if self.current_token.type is TokenType.extends:
            self.eat()  # eat EXTENDS
            parents.append(self.expr())
            while self.current_token.type is TokenType.comma:
                self.eat()  # eat COMMA
                parents.append(self.expr())
        self.eat(TokenType.colon)
        body = self._block(self._entity_body)
        return EntityTemplateDef(name, parents, body, **pos)

    def formatted_str(self):
        """formatted_str := (STRING_BODY | (DOLLAR_LBRACE expr RBRACE))*"""
        pos = self.current_pos
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
        return FormattedStr(res, **pos)

    def command_stmt(self):
        """command_stmt := COMMAND_BEGIN formatted_str COMMAND_END"""
        pos = self.current_pos
        self.eat(TokenType.command_begin)
        content = self.formatted_str()
        self.eat(TokenType.command_end)
        return Command(content, **pos)

    def module_meta(self):
        """module_meta := POINT* IDENTIFIER (POINT IDENTIFIER)*"""
        # leading dots
        leadint_dots = 0
        while self.current_token.type is TokenType.point:
            leadint_dots += 1
            self.eat()
        # at least one name should be given
        names = [self.current_token.value]
        self.eat(TokenType.identifier)
        # read more names
        while self.current_token.type is TokenType.point:
            self.eat()
            names.append(self.current_token.value)
            self.eat(TokenType.identifier)
        last_name = names.pop()
        return ModuleMeta(last_name, leadint_dots, names)

    def alias(self) -> Optional[str]:
        """Try to read an alias. Return None if no alias is given.
        alias := (AS IDENTIFIER)?
        """
        if self.current_token.type is TokenType.as_:
            self.eat()
            value = self.current_token.value
            self.eat(TokenType.identifier)
            return value
        return None

    def import_stmt(self):
        """import_stmt := IMPORT module_meta alias"""
        pos = self.current_pos
        self.eat(TokenType.import_)
        meta = self.module_meta()
        alias = self.alias()
        return Import(meta, alias, **pos)

    def from_import_stmt(self):
        """
        from_import_stmt := FROM module_meta IMPORT (STAR | (
          IDENTIFIER alias (COMMA IDENTIFIER alias)*
        ))
        """
        pos = self.current_pos
        self.eat(TokenType.from_)
        meta = self.module_meta()
        self.eat(TokenType.import_)
        if self.current_token.type is TokenType.star:
            self.eat()
            return FromImportAll(meta, **pos)
        else:
            names = [self.current_token.value]
            self.eat(TokenType.identifier)
            aliases = [self.alias()]
            while self.current_token.type is TokenType.comma:
                self.eat()
                names.append(self.current_token.value)
                self.eat(TokenType.identifier)
                aliases.append(self.alias())
            return FromImport(meta, names, aliases, **pos)

    def for_stmt(self):
        """
        for_stmt := FOR IDENTIFIER IN expr COLON statement_block
        """
        pos = self.current_pos
        self.eat(TokenType.for_)
        name = self.current_token.value
        self.eat(TokenType.identifier)
        self.eat(TokenType.in_)
        expr = self.expr()
        self.eat(TokenType.colon)
        body = self.statement_block()
        return For(name, expr, body, **pos)

    def _struct_body(self):
        pos = self.current_pos
        if self.current_token.type is TokenType.identifier:
            name = self.current_token.value
            self.eat()
            self.eat(TokenType.colon)
            type_ = self.type_spec()
            res = StructField(name, type_, **pos)
        else:
            res = self.pass_stmt()
        self.eat(TokenType.new_line)
        return res

    def struct_stmt(self):
        """
        struct_field_decl := IDENTIFIER (COLON type_spec)? EQUAL expr
        struct_body := ((struct_field_decl | pass_stmt) NEW_LINE)*
        struct_stmt := STRUCT IDENTIFIER (EXTENDS expr (COMMA expr)*)?
          COLON block{struct_body}
        """
        pos = self.current_pos
        self.eat(TokenType.struct)
        name = self.current_token.value
        self.eat(TokenType.identifier)
        bases = []
        if self.current_token.type is TokenType.extends:
            self.eat()  # eat EXTENDS
            bases.append(self.expr())
            while self.current_token.type is TokenType.comma:
                self.eat()  # eat COMMA
                bases.append(self.expr())
        self.eat(TokenType.colon)
        body = self._block(self._struct_body)
        return StructDef(name, bases, body, **pos)

    def _constant_decl(self) -> Tuple[str, Optional[TypeSpec], Expression]:
        """constant_decl := IDENTIFIER (COLON type_spec)? EQUAL expr"""
        name = self.current_token.value
        self.eat(TokenType.identifier)
        if self.current_token.type is TokenType.colon:
            self.eat()
            type_ = self.type_spec()
        else:
            type_ = None
        self.eat(TokenType.equal)
        value = self.expr()
        return (name, type_, value)

    def _handle_const(self):
        """
        constant_def_body := list_of{constant_decl} |
          paren_list_of{LPAREN, constant_decl, RPAREN}
        const_statement := const_def_stmt | (CONST constant_def_body NEW_LINE)
        """
        self.peek()
        if self.next_token.type is TokenType.def_:
            return self.const_def_stmt()
        pos = self.current_pos
        self.eat()  # eat CONST
        names = []
        types = []
        values = []
        def _add_const_decl():
            name, type_, value = self._constant_decl()
            names.append(name)
            types.append(type_)
            values.append(value)
        if self.current_token.type is TokenType.lparen:
            self.paren_list_of(_add_const_decl)
        else:
            self.list_of(_add_const_decl)
        self.eat(TokenType.new_line)
        return ConstDef(names, types, values, **pos)

    def reference_def_stmt(self):
        """reference_def_stmt := AMPERSAND constant_decl"""
        pos = self.current_pos
        self.eat(TokenType.ampersand)
        return ReferenceDef(*self._constant_decl(), **pos)

    def result_stmt(self):
        """result_stmt := RESULT expr"""
        pos = self.current_pos
        self.eat(TokenType.result)
        return Result(self.expr(), **pos)

    def statement(self):
        """
        expr_statement := (
          var_def_stmt | auto_var_def_stmt | assign_stmt |
          aug_assign_stmt | expr_stmt
        )
        simple_statement := (
          pass_stmt | command_stmt | import_stmt | from_import_stmt |
          result_stmt
        )
        embedded_statement := (
          if_stmt | while_stmt | for_stmt | interface_stmt | def_stmt |
          entity_stmt | struct_stmt | inline_def_stmt
        )
        statement := ((simple_statement | expr_statement) NEW_LINE) |
          embedded_statement | const_statement
        """
        # Statements that start with special token
        TOK2STMT_EMBEDDED = {
            TokenType.if_: self.if_stmt,
            TokenType.while_: self.while_stmt,
            TokenType.interface: self.interface_stmt,
            TokenType.def_: self.def_stmt,
            TokenType.inline: self.inline_def_stmt,
            TokenType.entity: self.entity_stmt,
            TokenType.for_: self.for_stmt,
            TokenType.struct: self.struct_stmt
        }
        TOK2STMT_SIMPLE = {
            TokenType.pass_: self.pass_stmt,
            TokenType.command_begin: self.command_stmt,
            TokenType.import_: self.import_stmt,
            TokenType.from_: self.from_import_stmt,
            TokenType.ampersand: self.reference_def_stmt,
            TokenType.result: self.result_stmt,
        }
        if self.current_token.type is TokenType.const:
            return self._handle_const()
        stmt_method = TOK2STMT_SIMPLE.get(self.current_token.type)
        if stmt_method:
            res = stmt_method()
            self.eat(TokenType.new_line)
            return res
        stmt_method = TOK2STMT_EMBEDDED.get(self.current_token.type)
        if stmt_method:
            return stmt_method()

        # Other statements that starts with an expression
        pos = self.current_pos
        expr = self.expr()
        AUG_ASSIGN = {
            TokenType.plus_equal: Operator.add,
            TokenType.minus_equal: Operator.minus,
            TokenType.times_equal: Operator.multiply,
            TokenType.divide_equal: Operator.divide,
            TokenType.mod_equal: Operator.mod
        }

        if self.current_token.type is TokenType.equal:
            # assign_stmt := expr EQUAL expr
            self.eat()  # eat equal
            node = Assign(expr, self.expr(), **pos)
        elif self.current_token.type in AUG_ASSIGN:
            # aug_assign_stmt := expr (PLUS_EQUAL |
            #   MINUS_EQUAL | TIMES_EQUAL | DIVIDE_EQUAL | MOD_EQUAL) expr
            operator = AUG_ASSIGN[self.current_token.type]
            self.eat()  # eat operator
            node = AugmentedAssign(expr, operator, self.expr(), **pos)
        elif self.current_token.type is TokenType.colon:
            # var_def_stmt := identifier COLON type_spec (EQUAL expr)?
            self.eat()  # eat colon
            if not isinstance(expr, Identifier):
                self.error(ErrorType.INVALID_VARDEF_STMT, **pos)
            type_ = self.type_spec()
            if self.current_token.type is TokenType.equal:
                self.eat()  # eat equal
                value = self.expr()
            else:
                value = None
            node = VarDef(expr.name, type_, value, **pos)
        elif self.current_token.type is TokenType.walrus:
            # auto_var_def_stmt := identifier WALRUS expr
            self.eat()  # eat walrus
            if not isinstance(expr, Identifier):
                self.error(ErrorType.INVALID_VARDEF_STMT, **pos)
            node = AutoVarDef(expr.name, self.expr(), **pos)
        else:  # just an expr
            # expr_stmt := expr
            node = ExprStatement(expr, **pos)
        self.eat(TokenType.new_line)
        return node

    ## Other generators

    def module(self):
        """module := statement* END_MARKER"""
        pos = self.current_pos
        stmts = []
        while self.current_token.type != TokenType.end_marker:
            stmts.append(self.statement())
        return Module(stmts, **pos)

    def argument_table(self, allowed_ports: Tuple[FuncPortType],
                       type_required=True):
        """
        type_decl := COLON type_spec
        default_decl := EQUAL expr
        When `type_required`:
          arg_decl := func_port_qualifier IDENTIFIER
            ((type_decl | default_decl) | (type_decl default_decl))
        Else:
          arg_decl := func_port_qualifier IDENTIFIER type_decl?
            default_decl?
        argument_table := paren_list_of{LPAREN, arg_decl, RPAREN}
        """
        arg_table = ArgumentTable(**self.current_pos)
        got_default = False
        def _arg_decl():
            nonlocal got_default
            pos = self.current_pos
            # read qualifier
            qualifier = self._func_port_qualifier(allowed_ports)
            # read name
            name = self.current_token.value
            self.eat()  # eat identifier
            # read type
            type_ = None
            if self.current_token.type is TokenType.colon:
                self.eat()
                type_ = self.type_spec()
            port = FunctionPort(type_, qualifier, **pos)
            # read default
            default = None
            if self.current_token.type is TokenType.equal:
                self.eat()
                default = self.expr()
                got_default = True
            elif got_default:
                self.error(ErrorType.NONDEFAULT_ARG_AFTER_DEFAULT, **pos)
            # check
            if (not (port.type or default)) and type_required:
                self.error(ErrorType.DONT_KNOW_ARG_TYPE, **pos, arg=name)
            if name in arg_table.args:
                self.error(ErrorType.DUPLICATE_ARG_DEF, **pos, arg=name)
            # add arg
            arg_table.add_arg(name, port, default)
        self.paren_list_of(_arg_decl)
        return arg_table

    def type_spec(self):
        """type_spec := expr"""
        pos = self.current_pos
        return TypeSpec(self.expr(), **pos)

    def call_table(self):
        """
        arg := (IDENTIFIER EQUAL)? expr
        call_table := paren_list_of{LPAREN, arg, RPAREN}
        # Note this grammar does not show the fact that all keyword
        # arguments must be placed after positional arguments.
        """
        pos = self.current_pos
        args, keywords = [], {}
        got_keyword = False  # if a keyword argument has been read
        def _arg():
            nonlocal got_keyword
            self.peek()
            if self.next_token.type is TokenType.equal:
                # keyword
                got_keyword = True
                key = self.current_token.value
                pos = self.current_pos
                self.eat(TokenType.identifier)
                if key in keywords:  # if already exists
                    self.error(
                        ErrorType.ARG_MULTIPLE_VALUES, arg=key, **pos
                    )
                self.eat(TokenType.equal)
                keywords[key] = self.expr()
            else:  # positioned
                if got_keyword:
                    self.error(ErrorType.POSITIONED_ARG_AFTER_KEYWORD)
                args.append(self.expr())
        self.paren_list_of(_arg)
        return CallTable(args, keywords, **pos)

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
