# Parser for Acacia
from .error import *
from .tokenizer import *
from .ast import *
from .constants import *

__all__ = ['Parser']

class Parser:
    def __init__(self, tokenizer: Tokenizer):
        self.tokenizer = tokenizer
        self.current_token = self.tokenizer.get_next_token()
        # next_token: when using method `peek`, next token is reserved here
        self.next_token = None
    
    @property
    def current_pos(self):
        return {
            "lineno": self.current_token.lineno,
            "col": self.current_token.col
        }
    
    def error(self, err_type: ErrorType, lineno = None, col = None, **kwargs):
        lineno = self.current_pos['lineno'] if lineno is None else lineno
        col = self.current_pos['col'] if col is None else col
        raise Error(
            err_type,
            lineno = lineno, col = col,
            **kwargs
        )
    
    def eat(self, expect_token_type: TokenType = None):
        # move to next token
        # if expect_token_type is given, also check type of the old token
        if (expect_token_type is not None) and \
            (self.current_token.type != expect_token_type):
            self.error(ErrorType.UNEXPECTED_TOKEN, token = self.current_token)
        if self.next_token is None:
            self.current_token = self.tokenizer.get_next_token()
        else:
            self.current_token = self.next_token
            self.next_token = None
    
    def peek(self):
        # peek the next token and store at self.next_token
        if self.next_token is None:
            # only generate when not generated yet
            self.next_token = self.tokenizer.get_next_token()
    
    def _block(self, indent: int):
        # read a block (of many statements with given indent num)
        stmts = []
        while self.current_token.type != TokenType.end_marker:
            stmt = self.statement(indent)
            if stmt is not None:
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
            # So we do _skip_empty_lines here
            if self.current_token.type is TokenType.line_begin:
                if self.current_token.value < indent:
                    break
        # Python does not allow empty blocks, so it is in Acacia
        if not stmts:
            self.error(ErrorType.EMPTY_BLOCK)
        return stmts
    
    def _skip_empty_lines(self):
        # skip empty lines and put current_token on the line_begin
        # of first valid line
        self.peek()
        while (self.current_token.type is self.next_token.type is \
            TokenType.line_begin
        ):
            self.eat()
            self.peek()
    
    # Following are different AST generators
    ## Expression generator

    def literal(self):
        # read a Literal (literal int, bool, str)
        if self.current_token.type in (TokenType.integer, TokenType.string):
            node = Literal(
                self.current_token.value,
                **self.current_pos
            )
            self.eat()
            return node
        elif self.current_token.type in (TokenType.true, TokenType.false):
            node = Literal(
                self.current_token.type is TokenType.true,
                **self.current_pos
            )
            self.eat()
            return node
        self.error(ErrorType.UNEXPECTED_TOKEN, token = self.current_token)
    
    def identifier(self):
        # identifier := IDENTIFIER
        pos = self.current_pos
        token = self.current_token
        self.eat(TokenType.identifier)
        return Identifier(token.value, **pos)
    
    def raw_score(self):
        # read a RawScore
        # raw_score := BAR expr COLON expr BAR
        pos = self.current_pos
        self.eat(TokenType.bar)
        selector = self.expr()
        self.eat(TokenType.colon)
        objective = self.expr()
        self.eat(TokenType.bar)
        return RawScore(objective, selector, **pos)
    
    def expr_l1(self):
        # arg := (IDENTIFIER EQUAL)? expr
        # level 1 expression := (
        #   (LPAREN expr RPAREN) | literal | identifier | raw_score
        # )(
        #   (POINT IDENTIFIER) | (LPAREN (arg COMMA)* arg? RPAREN)
        # )*
        # Call, Attribute, Constant, Identifier, other expressions with braces
        if self.current_token.type in (
            TokenType.integer, TokenType.true,
            TokenType.false, TokenType.string
        ):
            node = self.literal()
        elif self.current_token.type is TokenType.identifier:
            node = self.identifier()
        elif self.current_token.type is TokenType.lparen:
            self.eat(TokenType.lparen)
            node = self.expr()
            self.eat(TokenType.rparen)
        elif self.current_token.type is TokenType.bar:
            node = self.raw_score()
        else:
            self.error(ErrorType.UNEXPECTED_TOKEN, token = self.current_token)
        # handle Attribute and Call part
        def _attribute(node):
            # make `node` an Attribute
            self.eat(TokenType.point)
            attr = self.current_token.value
            self.eat(TokenType.identifier)
            return Attribute(
                node, attr,
                lineno = node.lineno, col = node.col
            )
        
        def _call(node):
            # make `node` a Call
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
                    if key in keywords: # if already exists
                        self.error(
                            ErrorType.ARG_MULTIPLE_VALUES, arg = key, **pos
                        )
                    self.eat(TokenType.equal)
                    keywords[key] = self.expr()
                else: # positioned
                    if not accept_positioned:
                        self.error(ErrorType.POSITIONED_ARG_AFTER_KEYWORD)
                    args.append(self.expr())
                # read comma
                if self.current_token.type is TokenType.comma:
                    self.eat()
                else: break
            self.eat(TokenType.rparen)
            return Call(
                node, args, keywords,
                lineno = node.lineno, col = node.col
            )
        
        # start
        while True:
            if self.current_token.type is TokenType.point:
                node = _attribute(node)
            elif self.current_token.type is TokenType.lparen:
                node = _call(node)
            else: return node
    
    def expr_l2(self):
        # level 2 expression := ((PLUS | MINUS) expr_l2) | expr_l1
        pos = self.current_pos
        if self.current_token.type is TokenType.plus:
            self.eat()
            return UnaryOp(Operator.positive, self.expr_l2(), **pos)
        elif self.current_token.type is TokenType.minus:
            self.eat()
            return UnaryOp(Operator.negative, self.expr_l2(), **pos)
        else: # no unary operators
            return self.expr_l1()

    def expr_l3(self):
        # level 3 expression := expr_l2 ((TIMES | DEVIDE | MOD) expr_l2)*
        node = self.expr_l2()
        while True:
            token_type = self.current_token.type
            if token_type is TokenType.star:
                op = Operator.multiply
            elif token_type is TokenType.slash:
                op = Operator.divide
            elif token_type is TokenType.mod:
                op = Operator.mod
            else: # no valid operator found
                return node
            self.eat() # eat operator
            node = BinOp(
                node, op, self.expr_l2(),
                lineno = node.lineno, col = node.col
            )
    
    def expr_l4(self):
        # level 4 expression := expr_l3 ((ADD | MINUS) expr_l3)*
        node = self.expr_l3()
        while True:
            token_type = self.current_token.type
            if token_type is TokenType.plus:
                op = Operator.add
            elif token_type is TokenType.minus:
                op = Operator.minus
            else: # no valid operator found
                return node
            self.eat() # eat operator
            node = BinOp(
                node, op, self.expr_l3(),
                lineno = node.lineno, col = node.col
            )
    
    def expr_l5(self):
        # level 5 expression := expr_l4 ((
        #   EQUAL_TO | UNEQUAL_TO | GREATER | LESS | GREATER_EQUAL | LESS_EQUAL
        # ) expr_l4)*
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
        if operators: # if not empty
            return CompareOp(left, operators, operands, **pos)
        return left
    
    def expr_l6(self):
        # level 6 expression := (NOT expr_l6) | expr_l5
        pos = self.current_pos
        if self.current_token.type is TokenType.not_:
            self.eat()
            return UnaryOp(Operator.not_, self.expr_l6(), **pos)
        else: # no unary operators
            return self.expr_l5()
    
    def expr_l7(self):
        # level 7 expression := expr_l6 (AND expr_l6)*
        left = self.expr_l6()
        operands = []
        while self.current_token.type is TokenType.and_:
            self.eat() # eat and_
            operands.append(self.expr_l6())
        if operands: # if not empty
            operands.insert(0, left)
            return BoolOp(
                Operator.and_, operands,
                lineno = left.lineno, col = left.col
            )
        return left
    
    def expr_l8(self):
        # level 8 expression := expr_l7 (OR expr_l7)*
        left = self.expr_l7()
        operands = []
        while self.current_token.type is TokenType.or_:
            self.eat() # eat or_
            operands.append(self.expr_l7())
        if operands: # if not empty
            operands.insert(0, left)
            return BoolOp(
                Operator.or_, operands,
                lineno = left.lineno, col = left.col
            )
        return left
    
    # expr: keep updates with the highest level of expr method
    # this is to make sure other funcs always call the
    # highest level of expr (convenient when updating)
    expr = expr_l8

    ## Statement generator

    def if_stmt(self, origin_indent):
        # if_statement := IF expr COLON statement<indented>+
        #   (ELIF expr COLON statement<indented>+)*
        #   (ELSE COLON statement<indented>+)?
        indent = origin_indent + Config.indent
        pos = self.current_pos
        IF_EXTRA = (TokenType.elif_, TokenType.else_)
        def _if_extra() -> list:
            # if statement is defined recursively, so a recursion is needed
            # if_extra := (ELIF expr COLON statement<indented>+ if_extra?)
            #   | (ELSE COLON statement<indented>+)
            # return list of statements
            if self.current_token.type is TokenType.else_:
                self.eat()
                self.eat(TokenType.colon)
                return self._block(indent)
            self.eat(TokenType.elif_)
            condition = self.expr()
            self.eat(TokenType.colon)
            stmts = self._block(indent)
            # To allow empty lines before "elif" or "else"
            self._skip_empty_lines()
            # See if there's more "elif" or "else"
            else_stmts = []
            next_indent = self.current_token.value
            self.peek() # same as below; skip line_begin
            if (self.next_token.type in IF_EXTRA) and \
                (next_indent == origin_indent):
                self.eat() # eat line_begin
                else_stmts = _if_extra()
            return [If(condition, stmts, else_stmts, **self.current_pos)]
        # if_statement := IF expr COLON statement<indented>+ if_extra?
        self.eat(TokenType.if_)
        condition = self.expr()
        self.eat(TokenType.colon)
        stmts = self._block(indent)
        else_stmts = []
        next_indent = self.current_token.value
        self.peek() # current is line_begin, check next
        if self.next_token.type in IF_EXTRA and next_indent == origin_indent:
            self.eat() # eat this line_begin
            else_stmts = _if_extra()
        return If(condition, stmts, else_stmts, **pos)
    
    def pass_stmt(self):
        # pass_statement := PASS
        node = Pass(**self.current_pos)
        self.eat(TokenType.pass_)
        return node
    
    def interface_stmt(self, origin_indent):
        # interface_stmt := INTERFACE IDENTIFIER COLON statement<indented>+
        pos = self.current_pos
        self.eat(TokenType.interface)
        name = self.current_token.value
        self.eat(TokenType.identifier)
        self.eat(TokenType.colon)
        stmts = self._block(origin_indent + Config.indent)
        return InterfaceDef(name, stmts, **pos)
    
    def def_stmt(self, origin_indent):
        # def_stmt := DEF IDENTIFIER argument_table (ARROW expr)?
        #   COLON statement<indented>+
        pos = self.current_pos
        self.eat(TokenType.def_)
        name = self.current_token.value
        self.eat(TokenType.identifier)
        arg_table = self.argument_table()
        returns = None
        if self.current_token.type is TokenType.arrow:
            self.eat()
            returns = self.expr()
        self.eat(TokenType.colon)
        stmts = self._block(origin_indent + Config.indent)
        return FuncDef(name, arg_table, stmts, returns, **pos)
    
    def command_stmt(self):
        # command_stmt := COMMAND
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
        # result_stmt := RESULT expr
        pos = self.current_pos
        self.eat(TokenType.result)
        return Result(self.expr(), **pos)
    
    def import_statement(self):
        # import_statement := IMPORT POINT* IDENTIFIER (POINT IDENTIFIER)*
        pos = self.current_pos
        self.eat(TokenType.import_)
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
        return Import(leadint_dots, last_name, names, **pos)

    def statement(self, expect_indent = 0) -> (Statement or None):
        # statement := LINE_BEGIN (
        #   (expr ?(
        #     (EQUAL | ARROW | ADD_EQUAL | MINUS_EQUAL|
        #     TIMES_EQUAL | DIVIDE_EQUAL | MOD_EQUAL) expr
        #   )) | if_stmt | pass_stmt | interface_stmt | def_stmt |
        #   command_stmt | result_stmt | import_stmt
        # )
        # expect_indent:int what size of indent block should be
        # this function may return None to show that file ends
        # every time when this func ends, self.current_char falls on
        # either line_begin or end_marker
        self._skip_empty_lines()
        # a line_begin token is needed; check indent
        got_indent = self.current_token.value
        self.eat(TokenType.line_begin)
        if expect_indent != got_indent:
            self.error(
                ErrorType.WRONG_INDENT,
                got = got_indent, expect = expect_indent
            )
        # main part
        token_type = self.current_token.type
        if token_type is TokenType.end_marker:
            return None
        if token_type is TokenType.if_:
            return self.if_stmt(expect_indent)
        elif token_type is TokenType.pass_:
            return self.pass_stmt()
        elif token_type is TokenType.interface:
            return self.interface_stmt(expect_indent)
        elif token_type is TokenType.def_:
            return self.def_stmt(expect_indent)
        elif token_type is TokenType.command:
            return self.command_stmt()
        elif token_type is TokenType.result:
            return self.result_stmt()
        elif token_type is TokenType.import_:
            return self.import_statement()
        
        # other statements that starts with an expression
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
                self.error(ErrorType.INVALID_ASSIGN_TARGET)
        
        # assignable := attribute | identifier | raw_score
        if self.current_token.type is TokenType.equal:
            # assign_stmt := assignable EQUAL expr
            self.eat() # eat equal
            _check_assign_target(expr)
            return Assign(expr, self.expr(), **pos)
        elif self.current_token.type in AUG_ASSIGN:
            # aug_assign_stmt := assignable (PLUS_EQUAL |
            #   MINUS_EQUAL | TIMES_EQUAL | DIVIDE_EQUAL | MOD_EQUAL) expr
            operator = AUG_ASSIGN[self.current_token.type]
            self.eat() # eat operator
            _check_assign_target(expr)
            return AugmentedAssign(expr, operator, self.expr(), **pos)
        elif self.current_token.type is TokenType.arrow:
            # bind_stmt := (attribute | identifier) ARROW expr
            self.eat() # eat arrow
            if not isinstance(expr, (Attribute, Identifier)):
                self.error(ErrorType.INVALID_BIND_TARGET)
            right = self.expr() # get assign value
            return MacroBind(expr, right, **pos)
        else: # just an expr
            # expr_stmt := expr
            return ExprStatement(expr, **pos)

    ## Other generators

    def module(self):
        # parse a Module
        pos = self.current_pos
        stmts = []
        while self.current_token.type != TokenType.end_marker:
            stmt = self.statement(expect_indent = 0)
            if stmt is not None:
                stmts.append(stmt)
        return Module(stmts, **pos)
    
    def argument_table(self):
        # parse an ArgumentTable
        # type_decl := COLON expr
        # default_decl := EQUAL expr
        # arg_decl := IDENTIFIER ((type_decl | default_decl)
        #   | (type_decl default_decl))
        # argument_table := LPAREN (arg_decl COMMA)* arg_decl? RPAREN
        arg_table = ArgumentTable(**self.current_pos)
        self.eat(TokenType.lparen)
        while self.current_token.type is TokenType.identifier:
            name = self.current_token.value
            pos = self.current_pos
            self.eat() # eat identifier
            # read type
            type_ = None
            if self.current_token.type is TokenType.colon:
                self.eat()
                type_ = self.expr()
            # read default
            default = None
            if self.current_token.type is TokenType.equal:
                self.eat()
                default = self.expr()
            # check
            if not (type_ or default):
                self.error(ErrorType.DONT_KNOW_ARG_TYPE, **pos, arg = name)
            if name in arg_table.args:
                self.error(ErrorType.DUPLICATE_ARG_DEF, **pos, arg = name)
            # add arg
            arg_table.add_arg(name, type_, default)
            # eat comma
            if self.current_token.type is TokenType.comma:
                self.eat()
            else:
                break # no comma -> end
        self.eat(TokenType.rparen)
        return arg_table
