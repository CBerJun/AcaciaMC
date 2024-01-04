"""Minecraft Command Generator of Acacia."""

__all__ = ['Generator', 'Context']

from typing import Union, TYPE_CHECKING, Optional, List, Tuple, Callable, Dict
import contextlib

from acaciamc.ast import *
from acaciamc.error import *
from acaciamc.mccmdgen.expression import *
from acaciamc.mccmdgen.symbol import ScopedSymbolTable
from acaciamc.mccmdgen.mcselector import MCSelector
from acaciamc.mccmdgen.datatype import Storable, SupportsEntityField
import acaciamc.mccmdgen.cmds as cmds

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.datatype import DataType

FUNC_NONE = "none"
FUNC_INLINE = "inline"
FUNC_NORMAL = "normal"

COMPOP_SWAP = {
    # Used when swapping 2 operands in a comparison
    Operator.greater: Operator.less,
    Operator.greater_equal: Operator.less_equal,
    Operator.less: Operator.greater,
    Operator.less_equal: Operator.greater_equal,
    Operator.equal_to: Operator.equal_to,
    Operator.unequal_to: Operator.unequal_to
}

class Context:
    def __init__(self, compiler: "Compiler", scope: ScopedSymbolTable = None):
        self.compiler = compiler
        if scope is None:
            scope = ScopedSymbolTable(builtins=compiler.builtins)
        self.scope: ScopedSymbolTable = scope
        # current_function: the current function we are visiting
        self.current_function: \
            Optional[Union[AcaciaFunction, InlineFunction]] = None
        # inline_result: stores result expression of inline function
        # only exists when visiting inline functions.
        self.inline_result: Optional[AcaciaExpr] = None
        # function_state: "none" | "inline" | "normal"
        # stores type of the nearest level of function. If not in any
        # function, it is "none".
        self.function_state: str = FUNC_NONE
        # self_value: value of `self` keyword
        self.self_value: Optional[AcaciaExpr] = None

    def copy(self):
        res = Context(self.compiler, self.scope)
        res.current_function = self.current_function
        res.inline_result = self.inline_result
        res.function_state = self.function_state
        res.self_value = self.self_value
        return res

    def new_scope(self):
        self.scope = ScopedSymbolTable(self.scope, self.compiler.builtins)

class Generator(ASTVisitor):
    """Generates MC function from an AST for a single file."""
    def __init__(self, node: AST, main_file: cmds.MCFunctionFile,
                 file_name: str, compiler: "Compiler"):
        super().__init__()
        self.node = node
        self.compiler = compiler
        self.file_name = file_name
        self.current_file = main_file
        self.ctx = Context(compiler)
        # processing_node: prepared for showing errors
        # to know which AST we are passing (so that lineno and col are known)
        self.processing_node = self.node
        # node_depth: how deep we are in the tree (for debugging comments)
        self.node_depth: int = -1
        # current_tmp_scores: tmp scores allocated on current statement
        # see method `visit`.
        self.current_tmp_scores = []

    def parse(self):
        """Parse the AST and generate commands."""
        try:
            self.visit(self.node)
        except Error as err:
            self.error(err)

    def parse_as_module(self) -> AcaciaModule:
        """Parse the AST and return it as an `AcaciaModule`."""
        self.current_file.write_debug("## Start of module parsing")
        self.parse()
        self.current_file.write_debug("## End of module parsing")
        return AcaciaModule(self.ctx.scope, self.compiler)

    def fix_error_location(self, error: Error):
        error.location.linecol = (
            self.processing_node.lineno,
            self.processing_node.col
        )

    # --- INTERNAL USE ---

    def error_c(self, *args, **kwds):
        self.error(Error(*args, **kwds))

    def error(self, error: Error):
        if not error.location.file_set():
            error.location.file = self.file_name
        if not error.location.linecol_set():
            self.fix_error_location(error)
        raise error

    def check_assignable(self, value: AcaciaExpr):
        """Raise error when an `AcaciaExpr` can't be assigned."""
        if not isinstance(value, VarValue):
            self.error_c(ErrorType.INVALID_ASSIGN_TARGET)

    def register_symbol(
            self, target_node: Union[Identifier, Attribute, Result, Subscript],
            target_value: AcaciaExpr
        ):
        """Register a value to a symbol table according to AST.
        `target_value` is the value that the ast represents
        e.g. Identifier(name='a'), IntVar(...) ->
             self.ctx.scope.set('a', IntVar(...))
        """
        if isinstance(target_node, Identifier):
            self.ctx.scope.set(target_node.name, target_value)
        elif isinstance(target_node, Attribute):
            # get AttributeTable and register
            object_ = self.visit(target_node.object)
            # The attribute must exists when assigning to it.
            if not object_.attribute_table.is_defined(target_node.attr):
                self.error_c(ErrorType.HAS_NO_ATTRIBUTE,
                             value_type=str(object_.data_type),
                             attr=target_node.attr)
            object_.attribute_table.set(target_node.attr, target_value)
        elif isinstance(target_node, Result):
            if self.ctx.function_state == FUNC_INLINE:
                self.ctx.inline_result = target_value
            else:
                self.error_c(ErrorType.RESULT_BIND_OUT_OF_SCOPE)
        elif isinstance(target_node, Subscript):
            object_ = self.visit(target_node.object)
            subscripts = tuple(map(self.visit, target_node.subscripts))
            if not isinstance(object_, SupportsSetItem):
                self.error_c(ErrorType.NO_SETITEM,
                             type_=str(object_.data_type))
            commands = object_.setitem(subscripts, target_value)
            if commands is not None:
                self.current_file.extend(commands)
        else:
            raise TypeError

    def node_location(self, node: AST) -> SourceLocation:
        return SourceLocation(self.file_name, (node.lineno, node.col))

    def write_debug(self, comment: str,
                    target: Optional[cmds.MCFunctionFile] = None):
        """Write debug comment to a file."""
        if target is None:
            target = self.current_file
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
    def set_mcfunc_file(self, file: cmds.MCFunctionFile):
        old = self.current_file
        self.current_file = file
        yield
        self.current_file = old

    @contextlib.contextmanager
    def new_mcfunc_file(self, path: Optional[str] = None):
        """Create a new mcfunction file and set it to current file."""
        f = cmds.MCFunctionFile()
        with self.set_mcfunc_file(f):
            yield f
            if f.has_content():
                self.compiler.add_file(f, path)

    @contextlib.contextmanager
    def set_ctx(self, ctx: Context):
        old = self.ctx
        self.ctx = ctx
        yield
        self.ctx = old

    @contextlib.contextmanager
    def new_ctx(self):
        with self.set_ctx(self.ctx.copy()):
            yield

    # --- VISITORS ---

    def visit(self, node: AST, **kwargs):
        # store which node we are passing now
        old_node = self.processing_node
        self.processing_node = node
        self.node_depth += 1  # used by `self.write_debug`
        if isinstance(node, Statement):
            # NOTE `current_tmp_scores` is modified by `Compiler`, to
            # tell the tmp scores that are allocated in this statement
            # so that we can free them when the statement ends.
            # Therefore, only update tmp scores when node is a
            # `Statement`.
            old_tmp_scores = self.current_tmp_scores
            self.current_tmp_scores = []
        # write debug
        if node.show_debug:
            self.write_debug(type(node).__name__)
        # visit the node
        res = super().visit(node, **kwargs)
        # set back node info
        self.processing_node = old_node
        self.node_depth -= 1
        if isinstance(node, Statement):
            # free used vars
            for score in self.current_tmp_scores:
                self.compiler.free_tmp(score)
            self.current_tmp_scores = old_tmp_scores
        return res

    def visit_Module(self, node: Module):
        # start
        for stmt in node.body:
            self.visit(stmt)

    # --- STATEMENT VISITORS ---

    def visit_VarDef(self, node: VarDef):
        # Analyze data type
        dt: DataType = self.visit(node.type)
        # Create variable
        if not isinstance(dt, Storable):
            self.error_c(ErrorType.UNSUPPORTED_VAR_TYPE, var_type=str(dt))
        var = dt.new_var()
        self.register_symbol(node.target, var)
        if node.value is not None:
            self._assign(var, node.value)

    def visit_AutoVarDef(self, node: AutoVarDef):
        is_bind: bool = False
        # Analyze data type & handle rvalue
        if isinstance(node.value, Call):
            func, table = self._call_inspect(node.value)
            value = self._call_invoke(node.value, func, table)
            is_bind = isinstance(func, ConstructorFunction)
        else:
            value = self.visit(node.value)
        # Create variable
        dt = value.data_type
        if not isinstance(dt, Storable):
            self.error_c(ErrorType.UNSUPPORTED_VAR_TYPE, var_type=str(dt))
        if not is_bind:
            var = dt.new_var()
        else:  # Bind, no new var
            var = value
        self.register_symbol(node.target, var)
        # Assign
        if value is not None and not is_bind:
            self.current_file.extend(value.export(var))

    def _assign(self, target: AcaciaExpr, value_node: Expression):
        self.check_assignable(target)
        value_type: Optional[DataType] = None
        value: Optional[AcaciaExpr] = None
        ctor_cb = None
        # analyze rvalue
        if isinstance(value_node, Call):
            func, table = self._call_inspect(value_node)
            if isinstance(func, ConstructorFunction):
                def ctor_cb():
                    commands.extend(func.initialize(target, *table))
                value_type = func.get_var_type()
            else:
                value = self._call_invoke(value_node, func, table)
        else:
            value = self.visit(value_node)
        # check type
        if value_type is None:
            assert value is not None
            value_type = value.data_type
        if not target.data_type.matches(value_type):
            self.error_c(
                ErrorType.WRONG_ASSIGN_TYPE,
                expect=str(target.data_type), got=str(value_type)
            )
        # assign
        commands = []
        if value is not None:
            commands.extend(value.export(target))
        else:
            assert ctor_cb is not None
            ctor_cb()
        # write commands
        self.current_file.extend(commands)

    def visit_Assign(self, node: Assign):
        target = self.visit(node.target)
        self._assign(target, node.value)

    def visit_AugmentedAssign(self, node: AugmentedAssign):
        # visit nodes
        target = self.visit(node.target)
        self.check_assignable(target)
        value = self.visit(node.value)
        # call target's methods
        M = {
            Operator.add: ('+=', 'iadd'),
            Operator.minus: ('-=', 'isub'),
            Operator.multiply: ('*=', 'imul'),
            Operator.divide: ('/=', 'idiv'),
            Operator.mod: ('%=', 'imod')
        }
        operator, method = M[node.operator]
        self.current_file.extend(self._wrap_method_op(
            operator, method, target, value
        ))

    def visit_Binding(self, node: Binding):
        # analyze value
        value = self.visit(node.value)
        # register to symbol table
        self.register_symbol(node.target, value)

    def visit_ExprStatement(self, node: ExprStatement):
        self.visit(node.value)

    def visit_Pass(self, node: Pass):
        pass

    def visit_FormattedStr(self, node: FormattedStr) -> str:
        res: List[str] = []
        for section in node.content:
            # expressions in commands need to be parsed
            if isinstance(section, str):
                res.append(section)
            else:
                expr = self.visit(section)
                try:
                    value = expr.cmdstr()
                except NotImplementedError:
                    err = Error(ErrorType.INVALID_FEXPR)
                    err.location.linecol = (section.lineno, section.col)
                    self.error(err)
                res.append(value)
        return ''.join(res)

    def visit_Command(self, node: Command):
        command = cmds.Cmd(self.visit(node.content), suppress_special_cmd=True)
        self.current_file.write(command)

    def visit_If(self, node: If):
        # condition
        condition = self.visit(node.condition)
        if not condition.data_type.matches_cls(BoolDataType):
            self.error_c(ErrorType.WRONG_IF_CONDITION,
                         got=str(condition.data_type))
        # optimization: if condition is a constant, just run the code
        if isinstance(condition, BoolLiteral):
            run_node = node.body if condition.value else node.else_body
            for stmt in run_node:
                self.visit(stmt)
            return
        # process body
        with self.new_mcfunc_file() as body_file:
            self.write_debug('If body')
            for stmt in node.body:
                self.visit(stmt)
        with self.new_mcfunc_file() as else_body_file:
            self.write_debug('Else branch of If')
            for stmt in node.else_body:
                self.visit(stmt)
        has_else = else_body_file.has_content()
        if (not has_else and isinstance(condition, SupportsAsExecute)):
            # optimization for SupportsAsExecute (when there is no
            # "else" branch)
            dependencies, subcmds = condition.as_execute()
            self.current_file.extend(dependencies)
            self.current_file.write(cmds.Execute(
                subcmds, runs=cmds.InvokeFunction(body_file)
            ))
            return
        dependencies, condition_var = to_BoolVar(condition, tmp=False)
        self.current_file.extend(dependencies)
        if body_file.has_content():
            self.current_file.write(cmds.Execute(
                [cmds.ExecuteScoreMatch(condition_var.slot, "1")],
                runs=cmds.InvokeFunction(body_file)
            ))
        if has_else:
            self.current_file.write(cmds.Execute(
                [cmds.ExecuteScoreMatch(condition_var.slot, "0")],
                runs=cmds.InvokeFunction(else_body_file)
            ))

    def visit_While(self, node: While):
        # condition
        condition = self.visit(node.condition)
        if not condition.data_type.matches_cls(BoolDataType):
            self.error_c(ErrorType.WRONG_WHILE_CONDITION,
                         got=str(condition.data_type))
        # optimization: if condition is always False, ommit
        if isinstance(condition, BoolLiteral):
            if condition.value is False:
                self.write_debug(
                    'Skipped because the condition always evaluates to False'
                )
                return
            else:
                self.error_c(ErrorType.ENDLESS_WHILE_LOOP)
        if isinstance(condition, SupportsAsExecute):
            dependencies, subcmds = condition.as_execute()
        else:
            dependencies, condition_var = to_BoolVar(condition, tmp=False)
            subcmds = [cmds.ExecuteScoreMatch(condition_var.slot, "1")]
        # body
        with self.new_mcfunc_file() as body_file:
            self.write_debug('While definition')
            body_file.write_debug('## Part 1. Body')
            for stmt in node.body:
                self.visit(stmt)
        # trigering the function
        if body_file.has_content():  # continue when body is not empty
            def _write_condition(file: cmds.MCFunctionFile):
                file.extend(dependencies)
                file.write(cmds.Execute(
                    subcmds, runs=cmds.InvokeFunction(body_file)
                ))
            # Keep recursion if condition is True
            body_file.write_debug('## Part 2. Recursion')
            _write_condition(body_file)
            # Only start the function when condition is True
            _write_condition(self.current_file)
        else:
            self.write_debug('No commands generated')

    def visit_InterfaceDef(self, node: InterfaceDef):
        path = '/'.join(node.path)
        if self.compiler.is_reserved_path(path):
            self.error_c(ErrorType.RESERVED_INTERFACE_PATH, path=path)
        location = self.compiler.lookup_interface(path)
        if location is not None:
            err = Error(ErrorType.DUPLICATE_INTERFACE, path=path)
            err.add_frame(ErrFrame(location, "First occurrence", note=None))
            self.error(err)
        self.compiler.add_interface(path, self.node_location(node))
        with self.new_ctx():
            self.ctx.new_scope()
            # body
            with self.new_mcfunc_file(path) as body_file:
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
                    types[arg] = defaults[arg].data_type
            else:  # type is given
                types[arg] = self.visit(type_node)
                # make sure default value matches type
                # e.g. `def f(a: int = True)`
                if (defaults[arg] is not None
                    and not types[arg].is_type_of(defaults[arg])):
                    self.error_c(
                        ErrorType.UNMATCHED_ARG_DEFAULT_TYPE,
                        arg=arg, arg_type=str(types[arg]),
                        default_type=str(defaults[arg].data_type)
                    )
        return args, types, defaults

    def visit_TypeSpec(self, node: TypeSpec):
        type_ = self.visit(node.content)
        try:
            dt = type_.datatype_hook()
        except NotImplementedError:
            raise Error(ErrorType.INVALID_TYPE_SPEC, got=str(type_.data_type))
        return dt

    def visit_CallTable(self, node: CallTable):
        args: List[AcaciaExpr] = []
        keywords: Dict[str, AcaciaExpr] = {}
        for value in node.args:
            args.append(self.visit(value))
        for arg, value in node.keywords.items():
            keywords[arg] = self.visit(value)
        return args, keywords

    def _func_expr(self, node: FuncDef) -> AcaciaFunction:
        """Return the function object to a function definition
        without parsing the body.
        """
        # get return type (of DataType type)
        if node.returns is None:
            returns = NoneDataType(self.compiler)
        else:
            returns = self.visit(node.returns)
        # check result type
        if not isinstance(returns, Storable):
            self.error_c(ErrorType.UNSUPPORTED_RESULT_TYPE,
                            result_type=str(returns))
        # parse arg
        args, types, defaults = self.visit(node.arg_table)
        # check argument type
        for name, value in types.items():
            if not isinstance(value, Storable):
                self.error_c(ErrorType.UNSUPPORTED_ARG_TYPE,
                             arg=name, arg_type=str(value))
        # create function
        return AcaciaFunction(
            name=node.name, args=args, arg_types=types, arg_defaults=defaults,
            returns=returns, compiler=self.compiler,
            source=self.node_location(node)
        )

    @contextlib.contextmanager
    def _in_noninline_func(self, func: AcaciaFunction):
        with self.new_ctx():
            self.ctx.new_scope()
            self.ctx.current_function = func
            self.ctx.function_state = FUNC_NORMAL
            yield

    def handle_inline_func(self, node: InlineFuncDef) -> InlineFunction:
        # Return the inline function object to a function definition
        if node.returns is None:
            returns = None
        else:
            returns = self.visit(node.returns)
        args, types, defaults = self.visit(node.arg_table)
        return InlineFunction(
            node, args, types, defaults, returns, self.ctx, owner=self,
            compiler=self.compiler, source=self.node_location(node)
        )

    def visit_FuncDef(self, node: FuncDef):
        func = self._func_expr(node)
        with self._in_noninline_func(func), \
             self.new_mcfunc_file() as body_file:
            # Register arguments to scope
            for arg, var in func.arg_vars.items():
                self.ctx.scope.set(arg, var)
            # Write file
            self.write_debug('Function definition of %s()' % node.name)
            for stmt in node.body:
                self.visit(stmt)
        # Add file
        if body_file.has_content():
            self.write_debug('Generated at %s' % body_file.get_path())
            func.file = body_file
        else:
            self.write_debug('No commands generated')
        self.ctx.scope.set(node.name, func)
        return func

    def visit_InlineFuncDef(self, node: InlineFuncDef):
        func = self.handle_inline_func(node)
        self.ctx.scope.set(node.name, func)

    def _parse_module(self, meta: ModuleMeta, lineno: int, col: int):
        try:
            res = self.compiler.parse_module(meta)
        except Error as err:
            err.add_frame(ErrFrame(
                SourceLocation(self.file_name, (lineno, col)),
                "Importing %s" % str(meta),
                note=None
            ))
            raise
        return res

    def visit_Import(self, node: Import):
        module, path = self._parse_module(node.meta, node.lineno, node.col)
        self.write_debug("Got module from %s" % path)
        self.ctx.scope.set(node.name, module)

    def visit_FromImport(self, node: FromImport):
        module, path = self._parse_module(node.meta, node.lineno, node.col)
        self.write_debug("Import from %s" % path)
        for name, alias in node.id2name.items():
            value = module.attribute_table.lookup(name)
            if value is None:
                self.error_c(ErrorType.MODULE_NO_ATTRIBUTE,
                             attr=name, module=str(node.meta))
            self.ctx.scope.set(alias, value)

    def visit_FromImportAll(self, node: FromImportAll):
        module, path = self._parse_module(node.meta, node.lineno, node.col)
        self.write_debug("Import everything from %s" % path)
        for name, value in module.attribute_table:
            self.ctx.scope.set(name, value)

    def visit_EntityTemplateDef(self, node: EntityTemplateDef):
        field_types = {}  # Field name to `DataType`
        field_metas = {}  # Field name to field meta
        methods = {}  # Method name to function `AcaciaExpr`
        method_qualifiers = {}  # Method name to qualifier
        metas = {}  # Meta name to value
        # Handle parents
        parents = []
        for parent_ast in node.parents:
            parent = self.visit(parent_ast)
            if not parent.data_type.matches_cls(ETemplateDataType):
                self.error_c(ErrorType.INVALID_ETEMPLATE,
                             got=str(parent.data_type))
            parents.append(parent)
        # If parent is not specified, use builtin `Entity`
        if not parents:
            parents.append(self.compiler.base_template)
        # 1st Pass: get all the attributes and give every non-inline
        # method a `MCFunctionFile` without parsing its body.
        methods_2ndpass: List[Tuple[AcaciaFunction, FuncDef]] = []
        for decl in node.body:
            res = self.visit(decl)
            if isinstance(decl, EntityField):
                # `res` is (field type, field meta)
                field_types[decl.name], field_metas[decl.name] = res
            elif isinstance(decl, EntityMethod):
                # `res` is `AcaciaFunction` or `InlineFunction`
                methods[decl.content.name] = res
                method_qualifiers[decl.content.name] = decl.qualifier
                if isinstance(res, AcaciaFunction):
                    methods_2ndpass.append((res, decl.content))
            elif isinstance(decl, EntityMeta):
                # `res` is (meta name, meta value)
                key, value = res
                if key in metas:
                    self.error_c(ErrorType.REPEAT_ENTITY_META, meta=key)
                metas[key] = value
        # generate the template before 2nd pass, since `self` value
        # needs the template specified.
        template = EntityTemplate(
            node.name, field_types, field_metas,
            methods, method_qualifiers, parents, metas,
            self.compiler, source=self.node_location(node)
        )
        # 2nd Pass: parse the non-inline method bodies.
        for method, ast in methods_2ndpass:
            with self._in_noninline_func(method):
                if ast.name in template.method_dispatchers:
                    t = template.method_dispatchers[ast.name].self_tag
                    self_var = TaggedEntity(t, template, self.compiler)
                else:
                    assert ast.name in template.simple_methods
                    self_var = template.simple_methods[ast.name].get_self_var()
                    assert self_var is not None
                self.ctx.self_value = self_var
                # Register arguments to scope
                for arg, var in method.arg_vars.items():
                    self.ctx.scope.set(arg, var)
                # Write file
                with self.set_mcfunc_file(method.file):
                    self.write_debug('Entity method definition of %s.%s()' %
                                     (node.name, ast.name))
                    for stmt in ast.body:
                        self.visit(stmt)
        # Register
        self.ctx.scope.set(node.name, template)

    def visit_EntityField(self, node: EntityField):
        data_type = self.visit(node.type)
        if not isinstance(data_type, SupportsEntityField):
            self.error_c(ErrorType.UNSUPPORTED_EFIELD_TYPE,
                         field_type=str(data_type))
        field_meta = data_type.new_entity_field()
        return data_type, field_meta

    def visit_EntityMethod(self, node: EntityMethod):
        content = node.content
        if isinstance(content, FuncDef):
            func = self._func_expr(content)
            # Give this function a file
            file = cmds.MCFunctionFile()
            func.file = file
            self.compiler.add_file(file)
        elif isinstance(content, InlineFuncDef):
            func = self.handle_inline_func(content)
        return func

    def visit_EntityMeta(self, node: EntityMeta):
        return node.name, self.visit(node.value)

    def visit_For(self, node: For):
        iterable = self.visit(node.expr)
        # for-in on an entity group has completely different meaning --
        # it is not a compile-time loop.
        if not iterable.data_type.matches_cls(EGroupDataType):
            try:
                items = iterable.iterate()
            except NotImplementedError:
                raise Error(ErrorType.NOT_ITERABLE,
                            type_=str(iterable.data_type))
            self.write_debug("Iterating over %d items" % len(items))
            for value in items:
                with self.new_ctx():
                    self.ctx.new_scope()
                    self.ctx.scope.set(node.name, value)
                    for stmt in node.body:
                        self.visit(stmt)
        else:
            assert isinstance(iterable, EntityGroup)
            with self.new_mcfunc_file() as body_file, \
                 self.new_ctx():
                self.ctx.new_scope()
                self.write_debug("Entity group iteration body")
                this = TaggedEntity.new_tag(iterable.template, self.compiler)
                executer = EntityReference(
                    MCSelector("s"), iterable.template, self.compiler
                )
                self.current_file.extend(executer.export(this))
                self.ctx.scope.set(node.name, this)
                for stmt in node.body:
                    self.visit(stmt)
            self.write_debug("Entity group iteration at %s"
                             % body_file.get_path())
            self.current_file.write(cmds.Execute(
                [cmds.ExecuteEnv("as", iterable.get_selector().to_str())],
                runs=cmds.InvokeFunction(body_file)
            ))

    def visit_StructField(self, node: StructField):
        # Check whether type is storable.
        data_type = self.visit(node.type)
        if not isinstance(data_type, Storable):
            self.error_c(ErrorType.UNSUPPORTED_SFIELD_TYPE,
                         field_type=str(data_type))
        return node.name, data_type

    def visit_StructDef(self, node: StructDef):
        base_structs = list(map(self.visit, node.bases))
        for i, base in enumerate(base_structs):
            if not isinstance(base, StructTemplate):
                err = Error(
                    ErrorType.INVALID_STEMPLATE, got=str(base.data_type)
                )
                err.location.linecol = node.bases[i].lineno, node.bases[i].col
                self.error(err)
        fields: Dict[str, "DataType"] = {}
        for decl in node.body:
            res = self.visit(decl)
            if isinstance(decl, StructField):
                name, type_ = res
                if name in fields:
                    raise Error(ErrorType.SFIELD_MULTIPLE_DEFS, name=name)
                fields[name] = type_
            else:
                assert isinstance(decl, Pass)
        self.ctx.scope.set(node.name, StructTemplate(
            node.name, fields, base_structs, self.compiler,
            source=self.node_location(node)
        ))

    # --- EXPRESSION VISITORS ---
    # literal

    def visit_Literal(self, node: Literal):
        value = node.value
        # NOTE Python bool is a subclass of int!!!
        if isinstance(value, bool):
            return BoolLiteral(value, self.compiler)
        elif isinstance(value, int):
            return IntLiteral(value, self.compiler)
        elif value is None:
            return NoneLiteral(self.compiler)
        elif isinstance(value, float):
            return Float(value, self.compiler)
        raise TypeError

    def visit_StrLiteral(self, node: StrLiteral):
        return String(self.visit(node.content), self.compiler)

    def visit_Self(self, node: Self):
        v = self.ctx.self_value
        if v is None:
            self.error_c(ErrorType.SELF_OUT_OF_SCOPE)
        return v

    def visit_ListDef(self, node: ListDef):
        return AcaciaList(list(map(self.visit, node.items)), self.compiler)

    def visit_MapDef(self, node: MapDef):
        keys = list(map(self.visit, node.keys))
        values = list(map(self.visit, node.values))
        return Map(keys, values, self.compiler)

    # assignable

    def visit_Identifier(self, node: Identifier):
        res = self.ctx.scope.lookup(node.name)
        # check undef
        if res is None:
            self.error_c(ErrorType.NAME_NOT_DEFINED, name=node.name)
        # return product
        return res

    def visit_Attribute(self, node: Attribute):
        value = self.visit(node.object)
        res = value.attribute_table.lookup(node.attr)
        # check undef
        if res is None:
            self.error_c(
                ErrorType.HAS_NO_ATTRIBUTE,
                value_type=str(value.data_type), attr=node.attr,
            )
        return res

    def visit_RawScore(self, node: RawScore):
        objective = self.visit(node.objective)
        selector = self.visit(node.selector)
        if not isinstance(objective, String):
            self.error_c(ErrorType.INVALID_RAWSCORE_OBJECTIVE,
                         got=str(objective.data_type))
        if isinstance(selector, String):
            selector_str = selector.value
        elif selector.data_type.matches_cls(EntityDataType):
            selector_str = selector.get_selector().to_str()
        else:
            self.error_c(ErrorType.INVALID_RAWSCORE_SELECTOR,
                         got=str(selector.data_type))
        return IntVar(
            cmds.ScbSlot(selector_str, objective.value),
            compiler=self.compiler
        )

    def visit_Result(self, node: Result):
        if self.ctx.function_state == FUNC_NORMAL:
            return self.ctx.current_function.result_var
        elif self.ctx.function_state == FUNC_INLINE:
            if self.ctx.inline_result is None:
                self.error_c(ErrorType.RESULT_UNDEFINED)
            return self.ctx.inline_result
        else:
            assert self.ctx.function_state == FUNC_NONE
            self.error_c(ErrorType.RESULT_OUT_OF_SCOPE)

    # operators

    def _wrap_op(self, operator: str, impl: Callable, *operands: AcaciaExpr):
        try:
            return impl(*operands)
        except TypeError:
            raise Error(
                ErrorType.INVALID_OPERAND,
                operator=operator,
                operand=", ".join(
                    '"%s"' % str(operand.data_type)
                    for operand in operands
                )
            )

    def _wrap_method_op(self, operator: str, method: str,
                        owner: AcaciaExpr, *operands: AcaciaExpr):
        def _empty_dummy(self, *operands):
            raise TypeError
        return self._wrap_op(
            operator, getattr(type(owner), method, _empty_dummy),
            owner, *operands
        )

    def visit_UnaryOp(self, node: UnaryOp):
        operand = self.visit(node.operand)
        operator = node.operator
        if operator in (Operator.positive, Operator.negative):
            return self._wrap_op(operator.value, OP2PYOP[operator], operand)
        elif operator is Operator.not_:
            return self._wrap_method_op(operator.value, "not_", operand)
        raise TypeError

    def visit_BinOp(self, node: BinOp):
        left, right = self.visit(node.left), self.visit(node.right)
        return self._wrap_op(
            node.operator.value,
            OP2PYOP[node.operator],
            left, right
        )

    def visit_CompareOp(self, node: CompareOp):
        compares = []
        left, right = None, self.visit(node.left)
        # split `e0 o1 e1 o2 e2 ... o(n) e(n)` into
        # `e0 o1 e1 and ... and e(n-1) o(n) e(n)`
        for operand, operator in zip(node.operands, node.operators):
            left, right = right, self.visit(operand)
            res = left.compare(operator, right)
            if res is NotImplemented:
                res = right.compare(COMPOP_SWAP[operator], left)
                if res is NotImplemented:
                    raise Error(
                        ErrorType.INVALID_OPERAND,
                        operator=operator.value,
                        operand='"%s", "%s"'
                                % (left.data_type, right.data_type)
                    )
            compares.append(res)
        return new_and_group(compares, self.compiler)

    def visit_BoolOp(self, node: BoolOp):
        operands = [self.visit(operand) for operand in node.operands]
        operator = node.operator
        # Make sure operands are all boolean
        for i, operand in enumerate(operands):
            if not operand.data_type.matches_cls(BoolDataType):
                err = Error(
                    ErrorType.INVALID_BOOLOP_OPERAND,
                    operator="and" if operator is Operator.and_ else "or",
                    operand=str(operand.data_type)
                )
                err_node = node.operands[i]
                err.location.linecol = (err_node.lineno, err_node.col)
                self.error(err)
        # Go
        if operator is Operator.and_:
            return new_and_group(operands, self.compiler)
        elif operator is Operator.or_:
            return new_or_expression(operands, self.compiler)
        raise TypeError

    # call

    def _call_inspect(self, node: Call) -> \
            Tuple[AcaciaCallable, Tuple[ARGS_T, KEYWORDS_T]]:
        func = self.visit(node.func)
        if not isinstance(func, AcaciaCallable):
            self.error_c(ErrorType.UNCALLABLE, expr_type=str(func.data_type))
        table = self.visit(node.table)
        return func, table

    def _call_invoke(self, node: Call, func: AcaciaCallable,
                     table: Tuple[ARGS_T, KEYWORDS_T]) -> AcaciaExpr:
        # call it
        res, commands = func.call_withframe(
            *table,
            location=self.node_location(node)
        )
        # write commands
        self.current_file.extend(commands)
        return res

    def visit_Call(self, node: Call):
        func, table = self._call_inspect(node)
        return self._call_invoke(node, func, table)

    def call_inline_func(self, func: InlineFunction,
                         args: ARGS_T, keywords: KEYWORDS_T) -> CALLRET_T:
        # We visit the AST node every time an inline function is called
        # Return a list of commands
        with self.set_ctx(func.context):
            self.ctx.inline_result = None
            self.ctx.current_function = func
            self.ctx.function_state = FUNC_INLINE
            # Register args directly into scope, without assigning
            # (as normal function calls do)
            arg2value = func.arg_handler.match(args, keywords)
            for arg, value in arg2value.items():
                self.ctx.scope.set(arg, value)
            # Visit body
            file = cmds.MCFunctionFile()
            with self.set_mcfunc_file(file):
                file.write_debug("## Start of inline function")
                for stmt in func.node.body:
                    self.visit(stmt)
                file.write_debug("## End of inline function")
                result = self.ctx.inline_result
        # Check result type
        expect = func.result_type
        if result is None:
            # didn't specify result
            if expect is None or expect.matches_cls(NoneDataType):
                result = NoneLiteral(self.compiler)
            else:
                self.error_c(ErrorType.NEVER_RESULT)
        got = result.data_type
        if (expect is not None) and (not expect.matches(got)):
            self.error_c(ErrorType.WRONG_RESULT_TYPE,
                         expect=str(expect), got=str(got))
        return result, file.commands

    # subscript

    def visit_Subscript(self, node: Subscript):
        object_ = self.visit(node.object)
        if not isinstance(object_, SupportsGetItem):
            self.error_c(ErrorType.NO_GETITEM,
                         type_=str(object_.data_type))
        subscripts = tuple(map(self.visit, node.subscripts))
        res = object_.getitem(subscripts)
        if isinstance(res, AcaciaExpr):
            expr = res
        else:
            expr, commands = res
            self.current_file.extend(commands)
        return expr

    # entity cast

    def visit_EntityCast(self, node: EntityCast):
        object_ = self.visit(node.object)
        template = self.visit(node.template)
        # Make sure `object_` is an entity
        if not object_.data_type.matches_cls(EntityDataType):
            self.error_c(ErrorType.INVALID_CAST_ENTITY,
                         got=str(object_.data_type))
        # Make sure `template` is a template
        if not template.data_type.matches_cls(ETemplateDataType):
            self.error_c(ErrorType.INVALID_ETEMPLATE,
                         got=str(template.data_type))
        # Make sure `template` is a super template of `object_`
        if not object_.template.is_subtemplate_of(template):
            self.error_c(ErrorType.INVALID_CAST)
        # Go
        return object_.cast_to(template)
