"""Parser for Acacia."""

__all__ = ['Parser']

from typing import Callable, Optional

from acaciamc.error import *
from acaciamc.tokenizer import *
from acaciamc.ast import *
from acaciamc.constants import *

class Parser:
    def __init__(self, tokenizer: Tokenizer):
        self.tokenizer = tokenizer
        self.current_token = self.tokenizer.get_next_token()
        self.next_token = None
        self.current_indent = 0

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
        err.set_location(lineno, col)
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
        """Read a block of structures.
        `func` reads the structure and should return the result AST.
        Every time when `func` ends, `self.current_char` should fall on
        either a `line_begin` or an `end_marker`.
        """
        stmts = []
        self.current_indent += Config.indent
        while self.current_token.type != TokenType.end_marker:
            # Check line_begin and indent
            self._skip_empty_lines()
            got_indent = self.current_token.value
            self.eat(TokenType.line_begin)
            if self.current_indent != got_indent:
                self.error(
                    ErrorType.WRONG_INDENT,
                    got=got_indent, expect=self.current_indent
                )
            if self.current_token.type is TokenType.end_marker:
                break
            # Parse the structure
            stmt = func()
            stmts.append(stmt)
            # every time statement method ends, current_token is
            # either line_begin or end_marker
            # when indent num is less than expected, end loop
            self._skip_empty_lines()
            # when a line is empty, the indent num is not considered; e.g.:
            # if a:
            #     b
            # # Empty line
            #     bc
            # So we do `_skip_empty_lines` here
            if self.current_token.type is TokenType.line_begin:
                if self.current_token.value < self.current_indent:
                    break
        self.current_indent -= Config.indent
        # Python does not allow empty blocks, so it is in Acacia
        if not stmts:
            self.error(ErrorType.EMPTY_BLOCK)
        return stmts

    def _skip_empty_lines(self):
        """Skip empty lines and put `self.current_token` on the
        `line_begin` of first valid line.
        """
        self.peek()
        while (self.current_token.type
               is self.next_token.type
               is TokenType.line_begin):
            self.eat()
            self.peek()

    def statement_block(self):
        """Read a block of statements."""
        return self._block(self.statement)

    # Following are different AST generators
    ## Expression generator

    def literal(self):
        """literal := INTEGER | STRING | TRUE | FALSE | NONE | FLOAT"""
        tok_type = self.current_token.type
        if tok_type in (TokenType.integer, TokenType.string, TokenType.float_):
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
        return Literal(value, **self.current_pos)

    def identifier(self):
        """identifier := IDENTIFIER"""
        pos = self.current_pos
        token = self.current_token
        self.eat(TokenType.identifier)
        return Identifier(token.value, **pos)

    def raw_score(self):
        """raw_score := BAR expr COLON expr BAR"""
        pos = self.current_pos
        self.eat(TokenType.bar)
        selector = self.expr()
        self.eat(TokenType.colon)
        objective = self.expr()
        self.eat(TokenType.bar)
        return RawScore(objective, selector, **pos)

    def self(self):
        """self := SELF"""
        pos = self.current_pos
        self.eat(TokenType.self)
        return Self(**pos)

    def expr_l0(self):
        """
        level 0 expression := (LPAREN expr RPAREN) | literal |
          identifier | raw_score
        """
        if self.current_token.type in (
            TokenType.integer, TokenType.float_, TokenType.true,
            TokenType.false, TokenType.string, TokenType.none
        ):
            return self.literal()
        elif self.current_token.type is TokenType.identifier:
            return self.identifier()
        elif self.current_token.type is TokenType.lparen:
            self.eat(TokenType.lparen)
            node = self.expr()
            self.eat(TokenType.rparen)
            return node
        elif self.current_token.type is TokenType.bar:
            return self.raw_score()
        elif self.current_token.type is TokenType.self:
            return self.self()
        else:
            self.error(ErrorType.UNEXPECTED_TOKEN, token=self.current_token)

    def expr_l1(self):
        """
        level 1 expression := expr_l0 (
          (POINT IDENTIFIER)
          | (LPAREN (arg COMMA)* arg? RPAREN)
          | AT expr_l0
        )*
        arg := (IDENTIFIER EQUAL)? expr
        """
        node = self.expr_l0()
        def _attribute(node: Expression):
            # make `node` an Attribute
            self.eat(TokenType.point)
            attr = self.current_token.value
            self.eat(TokenType.identifier)
            return Attribute(node, attr, lineno=node.lineno, col=node.col)

        def _call(node: Expression):
            # make `node` a `Call`
            args, keywords = [], {}
            self.eat(TokenType.lparen)
            # keywords are always after positioned args, so use this flag to
            # store if a keyword is read
            accept_positioned = True
            while self.current_token.type != TokenType.rparen:
                self.peek()
                if self.next_token.type is TokenType.equal:
                    # keyword
                    accept_positioned = False
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
                    if not accept_positioned:
                        self.error(ErrorType.POSITIONED_ARG_AFTER_KEYWORD)
                    args.append(self.expr())
                # read comma
                if self.current_token.type is TokenType.comma:
                    self.eat()
                else:
                    break
            self.eat(TokenType.rparen)
            return Call(
                node, args, keywords,
                lineno=node.lineno, col=node.col
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
        if_statement := IF expr COLON statement_block
          (ELIF expr COLON statement_block)*
          (ELSE COLON statement_block)?
        """
        pos = self.current_pos
        IF_EXTRA = (TokenType.elif_, TokenType.else_)
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
            self.eat(TokenType.elif_)
            condition = self.expr()
            self.eat(TokenType.colon)
            stmts = self.statement_block()
            # To allow empty lines before "elif" or "else"
            self._skip_empty_lines()
            # See if there's more "elif" or "else"
            else_stmts = []
            next_indent = self.current_token.value
            self.peek()  # same as below; skip line_begin
            if ((self.next_token.type in IF_EXTRA)
                and (next_indent == self.current_indent)):
                self.eat()  # eat line_begin
                else_stmts = _if_extra()
            return [If(condition, stmts, else_stmts, **self.current_pos)]
        # if_statement := IF expr COLON statement_block if_extra?
        self.eat(TokenType.if_)
        condition = self.expr()
        self.eat(TokenType.colon)
        stmts = self.statement_block()
        else_stmts = []
        next_indent = self.current_token.value
        self.peek()  # current is line_begin, check next
        if ((self.next_token.type in IF_EXTRA)
            and (next_indent == self.current_indent)):
            self.eat()  # eat this line_begin
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
        """pass_statement := PASS"""
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

    def def_stmt(self):
        """
        def_stmt := INLINE? DEF IDENTIFIER argument_table
          (ARROW type_spec)? COLON statement_block
        """
        pos = self.current_pos
        is_inline = self.current_token.type is TokenType.inline
        if is_inline:
            self.eat()  # eat "inline"
        self.eat(TokenType.def_)
        name = self.current_token.value
        self.eat(TokenType.identifier)
        # Inline functions does not require type declaration
        arg_table = self.argument_table(type_required=(not is_inline))
        returns = None
        if self.current_token.type is TokenType.arrow:
            self.eat()
            returns = self.type_spec()
        self.eat(TokenType.colon)
        stmts = self.statement_block()
        ast_class = InlineFuncDef if is_inline else FuncDef
        return ast_class(name, arg_table, stmts, returns, **pos)

    def _entity_body(self):
        pos = self.current_pos
        if self.current_token.type is TokenType.identifier:
            # field_decl
            name = self.current_token.value
            self.eat()  # eat IDENTIFIER
            self.eat(TokenType.colon)
            type_ = self.type_spec()
            return EntityField(name, type_, **pos)
        elif self.current_token.type is TokenType.at:
            # meta_decl
            self.eat()  # eat "@"
            name = self.current_token.value
            self.eat(TokenType.identifier)
            self.eat(TokenType.colon)
            value = self.expr()
            return EntityMeta(name, value, **pos)
        elif self.current_token.type is TokenType.pass_:
            return self.pass_stmt()
        else:
            # method_decl
            content = self.def_stmt()
            return EntityMethod(content, **pos)

    def entity_stmt(self):
        """
        entity_stmt := ENTITY IDENTIFIER (EXTENDS expr
          (COMMA expr)*)? COLON entity_body_block
        field_decl := IDENTIFIER COLON type_spec
        method_decl := def_stmt
        meta_decl := AT IDENTIFIER COLON expr
        entity_body := method_decl | field_decl | meta_decl | pass_stmt
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

    def command_stmt(self):
        """command_stmt := COMMAND"""
        pos = self.current_pos
        # NOTE the ${expressions} in COMMAND token need to be parsed
        res = []
        for section in self.current_token.value:
            if section[0] is StringMode.expression:
                # we need to parse section[1] by using another Parser
                # XXX which can be optimized
                parser = Parser(section[1])
                res.append((section[0], parser.expr()))
                parser.eat(TokenType.end_marker)
            else:
                res.append(section)
        self.eat(TokenType.command)
        return Command(res, **pos)

    def result_stmt(self):
        """result_stmt := RESULT expr"""
        pos = self.current_pos
        self.eat(TokenType.result)
        return Result(self.expr(), **pos)

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

    def alia(self) -> str:
        """Try to read an alia. Return None if no alia is given.
        alia := (AS IDENTIFIER)?
        """
        if self.current_token.type is TokenType.as_:
            self.eat()
            value = self.current_token.value
            self.eat(TokenType.identifier)
            return value
        return None

    def import_stmt(self):
        """import_stmt := IMPORT module_meta alia"""
        pos = self.current_pos
        self.eat(TokenType.import_)
        meta = self.module_meta()
        alia = self.alia()
        return Import(meta, alia, **pos)

    def from_import_stmt(self):
        """
        from_import_stmt := FROM module_meta IMPORT (STAR | (
          IDENTIFIER alia (COMMA IDENTIFIER alia)*
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
            alias = [self.alia()]
            while self.current_token.type is TokenType.comma:
                self.eat()
                names.append(self.current_token.value)
                self.eat(TokenType.identifier)
                alias.append(self.alia())
            return FromImport(meta, names, alias, **pos)

    def statement(self):
        """statement := LINE_BEGIN (
          (expr (
            (EQUAL | ARROW | ADD_EQUAL | MINUS_EQUAL|
            TIMES_EQUAL | DIVIDE_EQUAL | MOD_EQUAL) expr
          )?) | if_stmt | pass_stmt | interface_stmt | def_stmt |
          command_stmt | result_stmt | import_stmt |
          from_import_stmt | entity_stmt
        )
        """
        # Statements that start with special token
        TOK2STMT = {
            TokenType.if_: self.if_stmt,
            TokenType.while_: self.while_stmt,
            TokenType.pass_: self.pass_stmt,
            TokenType.interface: self.interface_stmt,
            TokenType.def_: self.def_stmt,
            TokenType.inline: self.def_stmt,
            TokenType.entity: self.entity_stmt,
            TokenType.command: self.command_stmt,
            TokenType.result: self.result_stmt,
            TokenType.import_: self.import_stmt,
            TokenType.from_: self.from_import_stmt
        }
        stmt_method = TOK2STMT.get(self.current_token.type)
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
        def _check_assign_target(node):
            # check if the assign target is valid
            if not isinstance(node, (Attribute, Identifier, RawScore)):
                self.error(ErrorType.INVALID_ASSIGN_TARGET, **pos)

        # assignable := attribute | identifier | raw_score
        if self.current_token.type is TokenType.equal:
            # assign_stmt := assignable EQUAL expr
            self.eat()  # eat equal
            _check_assign_target(expr)
            return Assign(expr, self.expr(), **pos)
        elif self.current_token.type in AUG_ASSIGN:
            # aug_assign_stmt := assignable (PLUS_EQUAL |
            #   MINUS_EQUAL | TIMES_EQUAL | DIVIDE_EQUAL | MOD_EQUAL) expr
            operator = AUG_ASSIGN[self.current_token.type]
            self.eat()  # eat operator
            _check_assign_target(expr)
            return AugmentedAssign(expr, operator, self.expr(), **pos)
        elif self.current_token.type is TokenType.arrow:
            # bind_stmt := (attribute | identifier) ARROW expr
            self.eat()  # eat arrow
            if not isinstance(expr, (Attribute, Identifier)):
                self.error(ErrorType.INVALID_BIND_TARGET)
            right = self.expr()  # get assign value
            return MacroBind(expr, right, **pos)
        else:  # just an expr
            # expr_stmt := expr
            return ExprStatement(expr, **pos)

    ## Other generators

    def module(self):
        pos = self.current_pos
        stmts = []
        while self.current_token.type != TokenType.end_marker:
            # Check line_begin and indent
            self._skip_empty_lines()
            got_indent = self.current_token.value
            self.eat(TokenType.line_begin)
            if self.current_indent != got_indent:
                self.error(
                    ErrorType.WRONG_INDENT,
                    got=got_indent, expect=self.current_indent
                )
            if self.current_token.type is TokenType.end_marker:
                break
            stmts.append(self.statement())
        return Module(stmts, **pos)

    def argument_table(self, type_required=True):
        """
        type_decl := COLON type_spec
        default_decl := EQUAL expr
        When `type_required`:
          arg_decl := IDENTIFIER ((type_decl | default_decl)
            | (type_decl default_decl))
        Else:
          arg_decl := IDENTIFIER type_decl? default_decl?
        argument_table := LPAREN (arg_decl COMMA)* arg_decl? RPAREN
        """
        arg_table = ArgumentTable(**self.current_pos)
        self.eat(TokenType.lparen)
        while self.current_token.type is TokenType.identifier:
            name = self.current_token.value
            pos = self.current_pos
            self.eat()  # eat identifier
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
            # check
            if (not (type_ or default)) and type_required:
                self.error(ErrorType.DONT_KNOW_ARG_TYPE, **pos, arg=name)
            if name in arg_table.args:
                self.error(ErrorType.DUPLICATE_ARG_DEF, **pos, arg=name)
            # add arg
            arg_table.add_arg(name, type_, default)
            # eat comma
            if self.current_token.type is TokenType.comma:
                self.eat()
            else:
                break  # no comma -> end
        self.eat(TokenType.rparen)
        return arg_table

    def type_spec(self):
        """type_spec := expr | (ENTITY (LPAREN expr RPAREN)?)"""
        pos = self.current_pos
        if self.current_token.type is TokenType.entity:
            self.eat()  # Eat "entity"
            if self.current_token.type is TokenType.lparen:
                self.eat()  # Eat "("
                template = self.expr()
                self.eat(TokenType.rparen)
            else:
                template = None
            return EntityTypeSpec(template, **pos)
        else:
            return TypeSpec(self.expr(), **pos)
