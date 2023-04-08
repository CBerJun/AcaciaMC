# Minecraft Command Generator of Acacia
import contextlib

from ..ast import *
from ..constants import Config
from ..error import *
from .expression import *
from .symbol import *

__all__ = ['MCFunctionFile', 'Generator']

# --- MCFUNCTIONFILE --- #
class MCFunctionFile:
    # an MCFunctionFile represents a .mcfunction file
    def __init__(self, path: str = None):
        # path:str the path of function from Config.function_folder
        # e.g. `lib/acalib3`, `main`
        self.commands = []
        self.set_path(path)
    
    def has_content(self):
        # return if there IS any commands in this file
        for line in self.commands:
            line = line.strip()
            if (not line.startswith('#')) and bool(line):
                return True
        return False
    
    # --- About Path ---
    def get_path(self):
        if self._path is None:
            raise ValueError('"path" attribute is not set yet')
        return self._path
    
    def set_path(self, path: str):
        self._path = path
    
    def is_path_set(self) -> bool:
        return self._path is not None
    
    # --- Export Methods ---

    def to_str(self) -> str:
        # make commands to str
        return '\n'.join(self.commands)
    
    def call(self) -> str:
        # return the command that runs this file
        return 'function %s/%s' % (Config.function_folder, self.get_path())

    # --- Write Methods ---
    
    def write(self, *commands: str):
        self.commands.extend(commands)
    
    def write_debug(self, *comments: str):
        # check enabled
        if not Config.debug_comments:
            return
        self.write(*comments)
    
    def extend(self, commands):
        # extend commands
        self.commands.extend(commands)

# --- GENERATOR --- #

class Generator(ASTVisitor):
    # A Generator generates code of an AST (a single file)
    def __init__(self, node: AST, main_file: MCFunctionFile, compiler):
        # compiler:Compiler
        # main_file:MCFunctionFile
        super().__init__()
        self.node = node
        self.compiler = compiler
        self.current_file = main_file
        self.current_scope = ScopedSymbolTable(builtins=self.compiler.builtins)
        # result_var: the var that stores result value
        # only exists when passing functions
        self.result_var = None
        # processing_node is prepared for showing errors
        # to know which AST we are passing (so that lineno and col are known)
        self.processing_node = self.node
        self.node_depth = -1 # how deep we are in the tree (for debug comment)
        # current_tmp_scores: tmp scores allocated on current statement
        # see method `visit`
        self.current_tmp_scores = []

    def parse(self):
        # parse the AST and generate commands
        self.visit(self.node)
    
    def parse_as_module(self) -> AcaciaModule:
        # parse the AST and return it as AcaciaModule
        self.current_file.write_debug("## Start of module parsing")
        self.parse()
        self.current_file.write_debug("## End of module parsing")
        return AcaciaModule(self.current_scope, self.compiler)
    
    # --- INTERNAL USE ---
    
    def check_assignable(self, value: AcaciaExpr):
        # check if a an AcaciaExpr is assignable
        if not isinstance(value, VarValue):
            self.compiler.error(ErrorType.UNASSIGNABLE)
    
    def register_symbol(self, target_node: AST, target_value: AcaciaExpr):
        # register a value to a SymbolTable according to AST
        # `target_value` is the value that the ast represents
        # e.g. Identifier(name='a'), IntVar(...) -> 
        #   self.current_scope.set('a', IntVar(...))
        if isinstance(target_node, Identifier):
            self.current_scope.set(target_node.name, target_value)
        elif isinstance(target_node, Attribute):
            # get AttributeTable and register
            object_ = self.visit(target_node.object)
            object_.attribute_table.set(target_node.attr, target_value)
        else: raise TypeError
    
    def get_result_type(self, node: Expression) -> Type:
        # Get result Type according to AST
        if node is None:
            return self.compiler.types[BuiltinNoneType]
        else:
            returns = self.visit(node)
            if not isinstance(returns.type, BuiltinTypeType):
                self.compiler.error(
                    ErrorType.INVALID_RESULT_TYPE, got = returns.type.name
                )
            return returns
    
    def write_debug(self, comment: str, target: MCFunctionFile = None):
        # write debug comment to current_file
        # target:MCFunctionFile the file to write comments into
        # (default self.current_file)
        # decide target
        target = self.current_file if target is None else target
        # write
        for comment_line in comment.split('\n'):
            target.write_debug(
                '# %s(%d:%d) %s' % (
                    ' ' * self.node_depth,
                    self.processing_node.lineno,
                    self.processing_node.col,
                    comment_line
                )
            )
    
    @contextlib.contextmanager
    def new_mcfunc_file(self, path: str = None):
        # Create a new mcfunction file
        f = MCFunctionFile(path)
        old = self.current_file
        self.current_file = f
        yield f
        if f.has_content():
            self.compiler.add_file(f)
        self.current_file = old
    
    @contextlib.contextmanager
    def new_scope(self):
        # Create a new scope
        old = self.current_scope
        s = ScopedSymbolTable(outer=old, builtins=self.compiler.builtins)
        self.current_scope = s
        yield s
        self.current_scope = old

    # --- VISITORS ---
    
    def visit(self, node: AST, **kwargs):
        # store which node we are passing now
        old_node = self.processing_node
        self.processing_node = node
        self.node_depth += 1 # used by self.write_debug
        if isinstance(node, Statement):
            # NOTE self.current_tmp_scores is modified by Compiler, to tell
            # the tmp scores that are allocated in this statement
            # so that we can free them when the statement ends
            # Therefore, only update tmp scores when node is a Statement
            old_tmp_scores = self.current_tmp_scores
            self.current_tmp_scores = []
        # write debug
        if not isinstance(node, (Expression, ArgumentTable)):
            self.write_debug(type(node).__name__)
        # visit the node
        res = super().visit(node, **kwargs)
        # set back node info
        self.processing_node = old_node
        self.node_depth -= 1
        if isinstance(node, Statement):
            # delete used vars
            for score in self.current_tmp_scores:
                self.compiler.free_tmp(*score)
            self.current_tmp_scores = old_tmp_scores
        return res
    
    def visit_Module(self, node: Module):
        # start
        for stmt in node.body:
            self.visit(stmt)
    
    ### --- visit Statement ---

    def visit_Assign(self, node: Assign):
        # analyze expr first
        value = self.visit(node.value)
        # then analyze target
        target = self.visit(node.target, check_undef = False)
        # for new defined var, analyze type and apply for score
        if target is None:
            ## apply a var according to type
            try:
                target = value.type.new_var()
            except NotImplementedError:
                self.compiler.error(
                    ErrorType.UNSUPPORTED_VAR_TYPE,
                    var_type = value.type.name
                )
            ## register the var to symbol table
            self.register_symbol(node.target, target)
        else: # for existed name, check if it is assignable
            self.check_assignable(target)
        # check type
        if target.type is not value.type:
            self.compiler.error(
                ErrorType.WRONG_ASSIGN_TYPE,
                expect = target.type.name, got = value.type.name
            )
        # assign
        # NOTE to avoid problems of changing var too early,
        # (e.g. a = 1 + a, we will let a = 1 first, and then plus 1
        # so whatever a is before assigning, it becomes 2 now)
        # we need a temporary var
        # (assign to tmp first and move it to target)
        # TODO analyze if expression uses target var
        # sometimes a temporary var is not needed
        tmp = target.type.new_var(tmp = True)
        self.current_file.extend(value.export(tmp))
        self.current_file.extend(tmp.export(target))
    
    def visit_AugmentedAssign(self, node: AugmentedAssign):
        # visit nodes
        target = self.visit(node.target, check_undef = True)
        self.check_assignable(target)
        value = self.visit(node.value)
        # call target's methods
        OP2METHOD = {
            Operator.add: 'iadd',
            Operator.minus: 'isub',
            Operator.multiply: 'imul',
            Operator.divide: 'idiv',
            Operator.mod: 'imod'
        }
        self.current_file.extend(
            getattr(target, OP2METHOD[node.operator])(value)
        )
    
    def visit_MacroBind(self, node: MacroBind):
        # analyze value
        value = self.visit(node.value)
        # register to symbol table
        self.register_symbol(node.target, value)
    
    def visit_ExprStatement(self, node: ExprStatement):
        expr = self.visit(node.value)
        self.current_file.extend(expr.export_novalue())
    
    def visit_Pass(self, node: Pass):
        pass
    
    def visit_Command(self, node: Command):
        # get exact command (without formatting)
        cmd = ''
        for section in node.values:
            # expressions in commands need to be parsed
            if section[0] is StringMode.expression:
                expr = self.visit(section[1])
                if not isinstance(expr.type, BuiltinStringType):
                    self.compiler.error(
                        ErrorType.INVALID_CMD_FORMATTING,
                        expr_type = expr.type.name
                    )
                cmd += expr.value
            elif section[0] is StringMode.text:
                cmd += section[1]
            else: raise ValueError
        self.current_file.write(cmd)
    
    def visit_If(self, node: If):
        # condition
        condition = self.visit(node.condition)
        if not isinstance(condition.type, BuiltinBoolType):
            self.compiler.error(
                ErrorType.WRONG_IF_CONDITION, got = condition.type.name
            )
        # optimization: if condition is a constant, just run the code
        if isinstance(condition, BoolLiteral):
            run_node = node.body if condition.value is True else node.else_body
            for stmt in run_node:
                self.visit(stmt)
            return
        dependencies, condition = to_BoolVar(condition)
        self.current_file.extend(dependencies) # add dependencies
        # process body
        with self.new_mcfunc_file() as body_file:
            self.write_debug('If body')
            for stmt in node.body:
                self.visit(stmt)
        if body_file.has_content():
            # only add command when some commands ARE generated
            self.current_file.write(export_execute_subcommands(
                subcmds = ['if score %s matches 1' % condition],
                main = body_file.call()
            ))
        # process else_bosy (almost same as above)
        with self.new_mcfunc_file() as else_body_file:
            self.write_debug('Else branch of If')
            for stmt in node.else_body:
                self.visit(stmt)
        if else_body_file.has_content():
            self.current_file.write(export_execute_subcommands(
                subcmds = ['if score %s matches 0' % condition],
                main = else_body_file.call()
            ))
    
    def visit_While(self, node: While):
        # condition
        condition = self.visit(node.condition)
        if not isinstance(condition.type, BuiltinBoolType):
            self.compiler.error(
                ErrorType.WRONG_WHILE_CONDITION, got = condition.type.name
            )
        # optimization: if condition is always False, ommit
        if isinstance(condition, BoolLiteral):
            if condition.value is False:
                self.write_debug(
                    'Skipped because the condition always evaluates to False'
                )
                return
            else:
                self.compiler.error(ErrorType.ENDLESS_WHILE_LOOP)
        # convert condition to BoolVar
        dependencies, condition = to_BoolVar(condition)
        # body
        with self.new_mcfunc_file() as body_file:
            self.write_debug('While definition')
            body_file.write_debug('## Part 1. Body')
            for stmt in node.body:
                self.visit(stmt)
        # trigering the function
        if body_file.has_content(): # continue when body is not empty
            def _write_condition(file: MCFunctionFile):
                file.extend(dependencies)
                file.write(export_execute_subcommands(
                    ['if score %s matches 1' % condition],
                    body_file.call()
                ))
            # Keep recursion if condition is True
            body_file.write_debug('## Part 2. Recursion')
            _write_condition(body_file)
            # Only start the function when condition is True
            _write_condition(self.current_file)
        else:
            self.write_debug('No commands generated')
    
    def visit_InterfaceDef(self, node: InterfaceDef):
        with self.new_scope():
            # body
            with self.new_mcfunc_file(
                'interface/%s' % '/'.join(node.path)
            ) as body_file:
                self.write_debug('Interface definition')
                for stmt in node.body:
                    self.visit(stmt)
            # add lib
            if body_file.has_content():
                self.write_debug('Generated at %s' % body_file.get_path())
            else:
                self.write_debug('No commands generated')
    
    def visit_ArgumentTable(self, node: ArgumentTable):
        # handle arg table
        args = node.args
        types = dict.fromkeys(args)
        defaults = dict.fromkeys(args)
        for arg in args:
            default_node = node.default[arg]
            type_node = node.types[arg]
            if default_node is not None:
                defaults[arg] = self.visit(default_node)
            if type_node is None:
                if default_node is not None:
                    # type is ommited, default value given
                    types[arg] = defaults[arg].type
            else: # type is given
                types[arg] = self.visit(type_node)
                # make sure specified type is a type
                # e.g. `def f(a: 1)`
                if not isinstance(types[arg].type, BuiltinTypeType):
                    self.compiler.error(
                        ErrorType.INVALID_ARG_TYPE,
                        arg = arg, arg_type = types[arg].type.name
                    )
                # make sure default value matches type
                # e.g. `def f(a: int = True)`
                if (defaults[arg] is not None and \
                    defaults[arg].type is not types[arg]):
                    self.compiler.error(
                        ErrorType.UNMATCHED_ARG_DEFAULT_TYPE,
                        arg = arg, arg_type = types[arg],
                        default_type = defaults[arg].type
                    )
        return args, types, defaults
    
    def visit_FuncDef(self, node: FuncDef):
        # get return type (of Type type)
        returns = self.get_result_type(node.returns)
        # parse arg
        args, types, defaults = self.visit(node.arg_table)
        # create function
        func = AcaciaFunction(
            args = args,
            arg_types = types,
            arg_defaults = defaults,
            returns = returns,
            compiler = self.compiler
        )
        self.current_scope.set(node.name, func)
        # read body
        old_res_var = self.result_var
        self.result_var = func.result_var
        with self.new_scope():
            # Register arguments to scope
            for arg in args:
                self.current_scope.set(arg, func.arg_vars[arg])
            # Write file
            with self.new_mcfunc_file() as body_file:
                self.write_debug('Function definition of %s()' % node.name)
                for stmt in node.body:
                    self.visit(stmt)
            # Add file
            if body_file.has_content():
                self.write_debug('Generated at %s' % body_file.get_path())
                func.file = body_file
            else:
                self.write_debug('No commands generated')
        # resume environment
        self.result_var = old_res_var
    
    def visit_InlineFuncDef(self, node: InlineFuncDef):
        returns = self.get_result_type(node.returns)
        args, types, defaults = self.visit(node.arg_table)
        func = InlineFunction(node, args, types, defaults,
                              returns, self.compiler)
        self.current_scope.set(node.name, func)
    
    def visit_Result(self, node: Result):
        # check
        if self.result_var is None:
            self.compiler.error(ErrorType.RESULT_OUT_OF_SCOPE)
        # visit expr and check type
        expr = self.visit(node.value)
        if expr.type is not self.result_var.type:
            self.compiler.error(
                ErrorType.WRONG_RESULT_TYPE,
                expect = self.result_var.type.name,
                got = expr.type.name
            )
        # write file
        self.current_file.extend(expr.export(self.result_var))
    
    def visit_Import(self, node: Import):
        module, path = self.compiler.parse_module(node.meta)
        self.write_debug("Got module from %s" % path)
        self.current_scope.set(node.name, module)
    
    def visit_FromImport(self, node: FromImport):
        module, path = self.compiler.parse_module(node.meta)
        self.write_debug("Import from %s" % path)
        for name, alia in node.id2name.items():
            value = module.attribute_table.lookup(name)
            if value is None:
                self.compiler.error(ErrorType.MODULE_NO_ATTRIBUTE, name=name)
            self.current_scope.set(alia, value)
    
    def visit_FromImportAll(self, node: FromImportAll):
        module, path = self.compiler.parse_module(node.meta)
        self.write_debug("Import everything from %s" % path)
        for name, value in module.attribute_table:
            self.current_scope.set(name, value)

    ### --- visit Expression ---
    # literal
    
    def visit_Literal(self, node: Literal):
        value = node.value
        # NOTE Python bool is a subclass of int!!!
        if isinstance(value, bool):
            return BoolLiteral(value, compiler = self.compiler)
        elif isinstance(value, int):
            return IntLiteral(value, compiler = self.compiler)
        elif isinstance(value, str):
            return String(value, compiler = self.compiler)
        elif value is None:
            return NoneLiteral(compiler = self.compiler)
        raise TypeError
    
    # assignable & bindable
    # check_undef:bool if True, raise Error when the assignable is
    # not found in SymbolTable; if False, return None when not found
    
    def visit_Identifier(self, node: Identifier, check_undef = True):
        res = self.current_scope.lookup(node.name)
        # check undef
        if res is None and check_undef:
            self.compiler.error(ErrorType.NAME_NOT_DEFINED, name = node.name)
        # return product
        return res
    
    def visit_Attribute(self, node: Attribute, check_undef = True):
        value = self.visit(node.object)
        res = value.attribute_table.lookup(node.attr)
        # check undef
        if res is None and check_undef:
            self.compiler.error(
                ErrorType.HAS_NO_ATTRIBUTE,
                value_type = value.type.name, attr = node.attr,
            )
        # return product
        return res
    
    def visit_RawScore(self, node: RawScore, check_undef = True):
        # a valid raw score always exists; `check_undef` is ommitted
        objective = self.visit(node.objective)
        selector = self.visit(node.selector)
        if not isinstance(objective, String):
            self.compiler.error(
                ErrorType.INVALID_RAWSCORE_OBJECTIVE, got = objective.type.name
            )
        if not isinstance(selector, String):
            self.compiler.error(
                ErrorType.INVALID_RAWSCORE_SELECTOR, got = selector.type.name
            )
        return IntVar(
            objective.value, selector.value,
            compiler = self.compiler, with_quote = False
        )

    # operators
    
    def visit_UnaryOp(self, node: UnaryOp):
        operand = self.visit(node.operand)
        if node.operator is Operator.positive:
            return + operand
        elif node.operator is Operator.negative:
            return - operand
        elif node.operator is Operator.not_:
            return operand.not_()
        raise TypeError
    
    def visit_BinOp(self, node: BinOp):
        left, right = self.visit(node.left), self.visit(node.right)
        if node.operator is Operator.add:
            return left + right
        elif node.operator is Operator.minus:
            return left - right
        elif node.operator is Operator.multiply:
            return left * right
        elif node.operator is Operator.divide:
            return left // right
        elif node.operator is Operator.mod:
            return left % right
        raise TypeError
    
    def visit_CompareOp(self, node: CompareOp):
        compares = [] # BoolCompare objects that are generated
        left, right = None, self.visit(node.left)
        # split `e0 o1 e1 o2 e2 ... o(n) e(n)` into
        # `e0 o1 e1 and ... and e(n-1) o(n) e(n)`
        for operand, operator in zip(node.operands, node.operators):
            left, right = right, self.visit(operand)
            compares.append(new_compare(
                left, operator, right, compiler = self.compiler
            ))
        return new_and_group(compares, compiler = self.compiler)
    
    def visit_BoolOp(self, node: BoolOp):
        operands = [self.visit(operand) for operand in node.operands]
        if node.operator is Operator.and_:
            return new_and_group(operands, compiler = self.compiler)
        elif node.operator is Operator.or_:
            return new_or_expression(operands, compiler = self.compiler)
        raise TypeError
    
    # call

    def visit_Call(self, node: Call) -> CallResult:
        # find called function
        func = self.visit(node.func)
        # process given args and keywords
        args, keywords = [], {}
        for value in node.args:
            args.append(self.visit(value))
        for arg, value in node.keywords.items():
            keywords[arg] = self.visit(value)
        # call it
        return func.call(args, keywords)
    
    def call_inline_func(self, func: InlineFunction, args, keywords: dict):
        # We visit the AST node every time an inline function is called
        # Return a list of commands
        with self.new_scope():
            # Register args directly into scope, without assigning
            # (as normal function calls do)
            arg2value = func.arg_handler.match(args, keywords)
            for arg, value in arg2value.items():
                self.current_scope.set(arg, value)
            # Visit body
            old_result = self.result_var
            self.result_var = func.result_var
            self.write_debug("Start of inline function")
            for stmt in func.node.body:
                self.visit(stmt)
            self.write_debug("End of inline function")
            self.result_var = old_result
