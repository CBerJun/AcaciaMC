"""Minecraft Command Generator of Acacia."""

__all__ = ['Generator', 'Context']

from typing import TYPE_CHECKING, Union, Optional, List, Tuple, Dict
import contextlib

from acaciamc.ast import *
from acaciamc.error import *
from acaciamc.objects import *
from acaciamc.mccmdgen.expr import *
from acaciamc.objects.none import ctdt_none
from acaciamc.mccmdgen.symbol import SymbolTable, CTRTConversionError
from acaciamc.mccmdgen.mcselector import MCSelector
from acaciamc.mccmdgen.datatype import *
from acaciamc.mccmdgen.ctexecuter import CTExecuter
from acaciamc.mccmdgen.ctexpr import CTObj, CTObjPtr
import acaciamc.mccmdgen.cmds as cmds

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.datatype import DataType
    from acaciamc.mccmdgen.ctexpr import CTDataType, CTExpr

FUNC_NONE = "none"
FUNC_INLINE = "inline"
FUNC_NORMAL = "normal"

OP2METHOD = {
    Operator.add: 'add',
    Operator.minus: 'sub',
    Operator.multiply: 'mul',
    Operator.divide: 'div',
    Operator.mod: 'mod',
    Operator.positive: 'unarypos',
    Operator.negative: 'unaryneg',
    Operator.not_: 'unarynot'
}

class Context:
    def __init__(self, compiler: "Compiler", scope: SymbolTable = None):
        self.compiler = compiler
        if scope is None:
            scope = SymbolTable(builtins=compiler.builtins)
        self.scope: SymbolTable = scope
        # current_function: the current function we are visiting
        self.current_function: \
            Optional[Union[AcaciaFunction, InlineFunction]] = None
        # inline_result: stores result expression of a function
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
        self.scope = SymbolTable(self.scope, self.compiler.builtins)

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

    def lookup_symbol(self, name: str, **options) -> Optional[AcaciaExpr]:
        try:
            return self.ctx.scope.lookup(name, **options)
        except CTRTConversionError as err:
            self.error_c(ErrorType.NON_RT_NAME, name=name,
                         type_=err.expr.cdata_type.name)

    def attribute_of(self, primary: AcaciaExpr, attr: str):
        try:
            return primary.attribute_table.lookup(attr)
        except CTRTConversionError as err:
            self.error_c(ErrorType.NON_RT_ATTR,
                         primary=str(primary.data_type), attr=attr,
                         type_=err.expr.cdata_type.name)

    def error_c(self, *args, **kwds):
        self.error(Error(*args, **kwds))

    def error(self, error: Error):
        if not error.location.file_set():
            error.location.file = self.file_name
        if not error.location.linecol_set():
            self.fix_error_location(error)
        raise error

    def error_node(self, node: AST, *args, **kwds):
        err = Error(*args, **kwds)
        err.location.linecol = (node.lineno, node.col)
        self.error(err)

    def register_symbol(self, name: str, value: AcaciaExpr):
        v = self.lookup_symbol(name, use_outer=False, use_builtins=False)
        if v is not None:
            self.error_c(ErrorType.SHADOWED_NAME, name=name)
        self.ctx.scope.set(name, value)

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

    def new_ctx(self):
        return self.set_ctx(self.ctx.copy())

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
        dt: DataType = self.visit(node.type)
        if not isinstance(dt, Storable):
            self.error_c(ErrorType.UNSUPPORTED_VAR_TYPE, var_type=str(dt))
        var = dt.new_var()
        self.register_symbol(node.target, var)
        if node.value is not None:
            self._assign(var, node.value)

    def visit_AutoVarDef(self, node: AutoVarDef):
        is_ctor: bool = False
        # Analyze data type & handle rvalue
        if isinstance(node.value, Call):
            func, table = self._call_inspect(node.value)
            value = self._call_invoke(node.value, func, table)
            is_ctor = isinstance(func, ConstructorFunction)
        else:
            value = self.visit(node.value)
        # Create variable
        dt = value.data_type
        if not isinstance(dt, Storable):
            self.error_c(ErrorType.UNSUPPORTED_VAR_TYPE, var_type=str(dt))
        if not is_ctor:
            var = dt.new_var()
        else:
            var = value
        self.register_symbol(node.target, var)
        # Assign
        if value is not None and not is_ctor:
            self.current_file.extend(value.export(var))

    def _assign(self, target: AcaciaExpr, value_node: Expression):
        if not target.is_assignable():
            self.error_c(ErrorType.INVALID_ASSIGN_TARGET)
        value_type: Optional[DataType] = None
        value: Optional[AcaciaExpr] = None
        ctor_cb = None
        # analyze rvalue
        if isinstance(value_node, Call):
            func, table = self._call_inspect(value_node)
            if (
                isinstance(func, ConstructorFunction)
                and target.data_type is func.get_var_type()
            ):
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
        method = f"i{OP2METHOD[node.operator]}"
        target = self.visit(node.target)
        value = self.visit(node.value)
        if not target.is_assignable():
            self.error_c(ErrorType.INVALID_ASSIGN_TARGET)
        # Call target's methods
        if hasattr(target, method):
            try:
                commands = getattr(target, method)(value)
            except TypeError:
                pass
            else:
                # Success
                self.current_file.extend(commands)
                return
        # Error
        self._op_error_s(f"{node.operator.value}=", target, value)

    def visit_ReferenceDef(self, node: ReferenceDef):
        value: AcaciaExpr = self.visit(node.value)
        if node.type is not None:
            dt: DataType = self.visit(node.type)
            if not dt.matches(value.data_type):
                self.error_c(ErrorType.WRONG_REF_TYPE,
                             anno=str(dt), got=str(value.data_type))
        if not value.is_assignable():
            self.error_node(node.value, ErrorType.CANT_REF)
        self.register_symbol(node.name, value)

    def visit_ConstDef(self, node: ConstDef):
        for name, type_, value in zip(node.names, node.types, node.values):
            v = self.visit(value)
            if not isinstance(v, ConstExpr):
                self.error_node(value, ErrorType.NOT_CONST, name=name)
            if type_ is not None:
                dt: DataType = self.visit(type_)
                if not dt.matches(v.data_type):
                    self.error_node(
                        value,
                        ErrorType.WRONG_CONST_TYPE,
                        name=name, anno=str(dt), got=str(v.data_type)
                    )
            self.register_symbol(name, v)

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
                    self.error_node(section, ErrorType.INVALID_FEXPR)
                res.append(value)
        return ''.join(res)

    def visit_Command(self, node: Command):
        command = cmds.Cmd(self.visit(node.content), suppress_special_cmd=True)
        self.current_file.write(command)

    def visit_If(self, node: If):
        # condition
        condition: AcaciaExpr = self.visit(node.condition)
        if not condition.data_type.matches_cls(BoolDataType):
            self.error_c(ErrorType.WRONG_IF_CONDITION,
                         got=str(condition.data_type))
        # process body
        with self.new_mcfunc_file() as body_file:
            self.write_debug('If body')
            for stmt in node.body:
                self.visit(stmt)
        has_then = body_file.has_content()
        with self.new_mcfunc_file() as else_body_file:
            self.write_debug('Else branch of If')
            for stmt in node.else_body:
                self.visit(stmt)
        has_else = else_body_file.has_content()
        if not has_then and not has_else:
            # no code in either branch
            return
        if has_then != has_else:
            new_cond = condition if has_then else condition.unarynot()
            if isinstance(new_cond, SupportsAsExecute):
                # optimization for SupportsAsExecute (when only one of
                # then/else is present)
                dependencies, subcmds = new_cond.as_execute()
                self.current_file.extend(dependencies)
                self.current_file.write(cmds.Execute(
                    subcmds, runs=cmds.InvokeFunction(
                        body_file if has_then else else_body_file
                    )
                ))
                return
        # optimization: if condition is a constant, just run the code
        if isinstance(condition, BoolLiteral):
            self.current_file.extend(
                body_file.commands if condition.value
                else else_body_file.commands
            )
            return
        # Fallback
        dependencies, condition_var = to_BoolVar(condition, tmp=False)
        self.current_file.extend(dependencies)
        if has_then:
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
        condition: AcaciaExpr = self.visit(node.condition)
        if not condition.data_type.matches_cls(BoolDataType):
            self.error_c(ErrorType.WRONG_WHILE_CONDITION,
                         got=str(condition.data_type))
        # body
        with self.new_mcfunc_file() as body_file:
            self.write_debug('While definition')
            body_file.write_debug('## Part 1. Body')
            for stmt in node.body:
                self.visit(stmt)
        # process condition
        if isinstance(condition, BoolLiteral):
            # optimize when condition is known at compile time
            if condition.value is False:
                self.write_debug(
                    'Skipped because the condition always evaluates to False'
                )
                return
            else:
                self.error_c(ErrorType.ENDLESS_WHILE_LOOP)
        if isinstance(condition, SupportsAsExecute):
            # optimization for `SupportsAsExecute`
            dependencies, subcmds = condition.as_execute()
        else:
            dependencies, condition_var = to_BoolVar(condition, tmp=False)
            subcmds = [cmds.ExecuteScoreMatch(condition_var.slot, "1")]
        # triggering the function
        if body_file.has_content():
            body_file.write_debug('## Part 2. Recursion')
            for file in (body_file, self.current_file):
                file.extend(dependencies)
                file.write(cmds.Execute(
                    subcmds, runs=cmds.InvokeFunction(body_file)
                ))
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

    def visit_FunctionPort(self, node: FunctionPort):
        return (
            None if node.type is None else self.visit(node.type),
            node.port
        )

    def visit_ArgumentTable(self, node: ArgumentTable):
        # handle arg table
        args = node.args
        types: Dict[str, Optional[DataType]] = dict.fromkeys(args)
        defaults: Dict[str, Optional[AcaciaExpr]] = dict.fromkeys(args)
        ports: Dict[str, FuncPortType] = {}
        for arg in args:
            default_node = node.default[arg]
            type_node = node.types[arg]
            if default_node is not None:
                defaults[arg] = self.visit(default_node)
            types[arg], ports[arg] = self.visit(type_node)
            # make sure default value matches type
            # e.g. `def f(a: int = True)`
            if (defaults[arg] is not None
                and types[arg] is not None
                and not types[arg].is_type_of(defaults[arg])):
                self.error_c(
                    ErrorType.UNMATCHED_ARG_DEFAULT_TYPE,
                    arg=arg, arg_type=str(types[arg]),
                    default_type=str(defaults[arg].data_type)
                )
        return args, types, defaults, ports

    def visit_TypeSpec(self, node: TypeSpec):
        type_ = self.visit(node.content)
        try:
            dt = type_.datatype_hook()
        except NotImplementedError:
            self.error_c(ErrorType.INVALID_TYPE_SPEC, got=str(type_.data_type))
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
        args, types, defaults, _ = self.visit(node.arg_table)
        # infer missing type specs
        for name in args:
            if types[name] is None:
                types[name] = defaults[name].data_type
        # make sure default values are constants
            if defaults[name] is None:
                continue
            if not isinstance(defaults[name], ConstExpr):
                self.error_node(
                    node.arg_table.default[name],
                    ErrorType.NONREF_ARG_DEFAULT_NOT_CONST, arg=name
                )
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
            returns = NoneDataType(self.compiler)
            res_port = FuncPortType.by_value
        else:
            returns, res_port = self.visit(node.returns)
        args, arg_types, arg_defaults, arg_ports = self.visit(node.arg_table)
        for arg, default in arg_defaults.items():
            if default is None:
                continue
            if arg_ports[arg] is FuncPortType.by_reference:
                if not default.is_assignable():
                    self.error_node(node.arg_table.default[arg],
                                    ErrorType.CANT_REF_ARG, arg=arg)
            else:
                if not isinstance(default, ConstExpr):
                    self.error_node(
                        node.arg_table.default[arg],
                        ErrorType.NONREF_ARG_DEFAULT_NOT_CONST, arg=arg
                    )
        return InlineFunction(
            node,
            args, arg_types, arg_defaults, arg_ports,
            returns, res_port, self.ctx, owner=self,
            compiler=self.compiler, source=self.node_location(node)
        )

    def handle_normal_func(self, node: FuncDef) -> AcaciaFunction:
        func = self._func_expr(node)
        with self._in_noninline_func(func), \
             self.new_mcfunc_file() as body_file:
            # Register arguments to scope
            for arg, var in func.arg_vars.items():
                self.register_symbol(arg, var)
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
        return func

    def handle_const_func(self, node: ConstFuncDef) -> AcaciaCTFunction:
        args = node.arg_table.args
        arg_types: Dict[str, Optional["CTDataType"]] = dict.fromkeys(args)
        defaults: Dict[str, Optional[CTObj]] = dict.fromkeys(args)
        ctexec = CTExecuter(self.ctx.scope, self, self.file_name)
        for arg in args:
            default_node = node.arg_table.default[arg]
            port_node = node.arg_table.types[arg]
            if default_node is not None:
                defaults[arg] = ctexec.visittop(default_node)
            if port_node is not None and port_node.type is not None:
                arg_types[arg] = ctexec.visittop(port_node.type)
            # make sure default value matches type
            # e.g. `def f(a: int = True)`
            if (
                defaults[arg] is not None
                and arg_types[arg] is not None
                and not arg_types[arg].is_typeof(defaults[arg])
            ):
                self.error_c(
                    ErrorType.UNMATCHED_ARG_DEFAULT_TYPE,
                    arg=arg, arg_type=arg_types[arg].name,
                    default_type=defaults[arg].cdata_type.name
                )
        if node.returns is None or node.returns.type is None:
            returns = ctdt_none
        else:
            returns = ctexec.visittop(node.returns.type)
        return AcaciaCTFunction(
            node, args, arg_types, defaults,
            returns, self.ctx, owner=self, compiler=self.compiler,
            source=self.node_location(node)
        )

    def visit_FuncDef(self, node: FuncDef):
        func = self.handle_normal_func(node)
        self.register_symbol(node.name, func)

    def visit_InlineFuncDef(self, node: InlineFuncDef):
        func = self.handle_inline_func(node)
        self.register_symbol(node.name, func)

    def visit_ConstFuncDef(self, node: ConstFuncDef):
        func = self.handle_const_func(node)
        self.register_symbol(node.name, func)

    def module_traced(self, meta: ModuleMeta, lineno: int, col: int):
        try:
            res = self.compiler.parse_module(meta, self.current_file)
        except Error as err:
            err.add_frame(ErrFrame(
                SourceLocation(self.file_name, (lineno, col)),
                "Importing %s" % str(meta),
                note=None
            ))
            raise
        return res

    def visit_Import(self, node: Import):
        module, path = self.module_traced(node.meta, node.lineno, node.col)
        self.write_debug("Got module from %s" % path)
        self.register_symbol(node.name, module)
        self.ctx.scope.no_export.add(node.name)

    def visit_FromImport(self, node: FromImport):
        module, path = self.module_traced(node.meta, node.lineno, node.col)
        self.write_debug("Import from %s" % path)
        for name, alias in node.id2name.items():
            value = self.attribute_of(module, name)
            if value is None:
                self.error_c(ErrorType.MODULE_NO_ATTRIBUTE,
                             attr=name, module=str(node.meta))
            self.register_symbol(alias, value)
        self.ctx.scope.no_export.update(node.id2name.values())

    def visit_FromImportAll(self, node: FromImportAll):
        module, path = self.module_traced(node.meta, node.lineno, node.col)
        self.write_debug("Import everything from %s" % path)
        for name in module.attribute_table.all_names():
            self.register_symbol(name, self.attribute_of(module, name))
            self.ctx.scope.no_export.add(name)

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
                # `res` is `AcaciaFunction`, `InlineFunction` or
                # `AcaciaCTFunction`
                methods[decl.content.name] = res
                method_qualifiers[decl.content.name] = decl.qualifier
                if (
                    isinstance(res, AcaciaFunction)
                    and decl.qualifier is not MethodQualifier.static
                ):
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
        # 2nd Pass: parse body of non-inline non-static methods.
        for method, ast in methods_2ndpass:
            with self._in_noninline_func(method):
                if ast.name in template.method_dispatchers:
                    disp = template.method_dispatchers[ast.name]
                    _, gself = disp.impls[method]
                    self_var = gself()
                else:
                    assert ast.name in template.simple_methods
                    self_var = template.simple_methods[ast.name].get_self_var()
                assert self_var is not None
                self.ctx.self_value = self_var
                # Register arguments to scope
                for arg, var in method.arg_vars.items():
                    self.register_symbol(arg, var)
                # Write file
                with self.set_mcfunc_file(method.file):
                    self.write_debug('Entity method definition of %s.%s()' %
                                     (node.name, ast.name))
                    for stmt in ast.body:
                        self.visit(stmt)
        # Register
        self.register_symbol(node.name, template)

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
            if node.qualifier is MethodQualifier.static:
                func = self.handle_normal_func(content)
            else:
                func = self._func_expr(content)
                # Give this function a file
                file = cmds.MCFunctionFile()
                func.file = file
                self.compiler.add_file(file)
        elif isinstance(content, InlineFuncDef):
            func = self.handle_inline_func(content)
        else:
            assert isinstance(content, ConstFuncDef)
            assert node.qualifier is MethodQualifier.static
            func = self.handle_const_func(content)
        func.source = self.node_location(node)
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
                self.error_c(ErrorType.NOT_ITERABLE,
                             type_=str(iterable.data_type))
            self.write_debug("Iterating over %d items" % len(items))
            for value in items:
                with self.new_ctx():
                    self.ctx.new_scope()
                    self.register_symbol(node.name, value)
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
                self.register_symbol(node.name, this)
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
                self.error_node(node.bases[i], ErrorType.INVALID_STEMPLATE,
                                got=str(base.data_type))
        fields: Dict[str, "DataType"] = {}
        for decl in node.body:
            res = self.visit(decl)
            if isinstance(decl, StructField):
                name, type_ = res
                if name in fields:
                    self.error_c(ErrorType.SFIELD_MULTIPLE_DEFS, name=name)
                fields[name] = type_
            else:
                assert isinstance(decl, Pass)
        self.register_symbol(node.name, StructTemplate(
            node.name, fields, base_structs, self.compiler,
            source=self.node_location(node)
        ))

    def visit_Result(self, node: Result):
        rt = self.ctx.current_function.result_type
        def _check(t: "DataType"):
            if rt is not None and not rt.matches(t):
                self.error_c(ErrorType.WRONG_RESULT_TYPE,
                             expect=str(rt), got=str(t))
        if self.ctx.function_state == FUNC_NORMAL:
            if isinstance(node.value, Call):
                func, table = self._call_inspect(node.value)
                if (isinstance(func, ConstructorFunction)
                        and rt is func.get_var_type()):
                    value = None
                else:
                    value = self._call_invoke(node.value, func, table)
            else:
                value = self.visit(node.value)
            rv = self.ctx.current_function.result_var
            if value is None:
                commands = func.initialize(rv, *table)
            else:
                _check(value.data_type)
                commands = value.export(rv)
            self.current_file.extend(commands)
        elif self.ctx.function_state == FUNC_INLINE:
            value: AcaciaExpr = self.visit(node.value)
            _check(value.data_type)
            p = self.ctx.current_function.result_port
            if p is FuncPortType.by_value:
                dt = value.data_type
                if not isinstance(dt, Storable):
                    self.error_c(ErrorType.UNSUPPORTED_RESULT_TYPE,
                                result_type=str(dt))
                if self.ctx.inline_result is None:
                    self.ctx.inline_result = dt.new_var()
                self.current_file.extend(value.export(self.ctx.inline_result))
            elif p is FuncPortType.by_reference:
                if self.ctx.inline_result is not None:
                    self.error_c(ErrorType.MULTIPLE_RESULTS)
                if not value.is_assignable():
                    self.error_c(ErrorType.CANT_REF_RESULT)
                self.ctx.inline_result = value
            else:
                assert p is FuncPortType.const
                if self.ctx.inline_result is not None:
                    self.error_c(ErrorType.MULTIPLE_RESULTS)
                if not isinstance(value, ConstExpr):
                    self.error_c(ErrorType.RESULT_NOT_CONST)
                self.ctx.inline_result = value
        else:
            assert self.ctx.function_state == FUNC_NONE
            self.error_c(ErrorType.RESULT_OUT_OF_SCOPE)

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

    def _ct_list(self, items: List[Expression]):
        res = []
        for item in items:
            r = self.visit(item)
            if not isinstance(r, ConstExpr):
                self.error_node(item, ErrorType.ELEMENT_NOT_CONST)
            res.append(r)
        return res

    def visit_ListDef(self, node: ListDef):
        return AcaciaList(self._ct_list(node.items), self.compiler)

    def visit_MapDef(self, node: MapDef):
        return Map(self._ct_list(node.keys),
                   self._ct_list(node.values), self.compiler)

    # assignable

    def visit_Identifier(self, node: Identifier):
        res = self.lookup_symbol(node.name)
        if res is None:
            self.error_c(ErrorType.NAME_NOT_DEFINED, name=node.name)
        return res

    def visit_Attribute(self, node: Attribute):
        value = self.visit(node.object)
        res = self.attribute_of(value, node.attr)
        if res is None:
            self.error_c(
                ErrorType.HAS_NO_ATTRIBUTE,
                value_type=str(value.data_type), attr=node.attr,
            )
        return res

    # operators

    def _op_error_s(self, operator: str, *operands: AcaciaExpr):
        self.error_c(
            ErrorType.INVALID_OPERAND,
            operator=operator,
            operand=", ".join(
                '"%s"' % operand.data_type
                for operand in operands
            )
        )

    def _op_error(self, operator: Operator, *operands: AcaciaExpr):
        self._op_error_s(operator.value, *operands)

    def _wrap_method_op(self, operator: str, method: str,
                        owner: AcaciaExpr, *operands: AcaciaExpr):
        if hasattr(owner, method):
            try:
                commands = getattr(owner, method)(*operands)
            except TypeError:
                pass
            else:
                return commands
        self._op_error(operator, owner, *operands)

    def visit_UnaryOp(self, node: UnaryOp):
        operand = self.visit(node.operand)
        try:
            res = getattr(operand, OP2METHOD[node.operator])()
        except TypeError:
            self._op_error(node.operator, operand)
        return res

    def visit_BinOp(self, node: BinOp):
        left, right = self.visit(node.left), self.visit(node.right)
        meth = OP2METHOD[node.operator]
        try:
            res = getattr(left, meth)(right)
        except TypeError:
            try:
                res = getattr(right, f"r{meth}")(left)
            except TypeError:
                self._op_error(node.operator, left, right)
        return res

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
                    self.error_c(
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
                self.error_node(
                    node.operands[i],
                    ErrorType.INVALID_BOOLOP_OPERAND,
                    operator=operator.value,
                    operand=str(operand.data_type)
                )
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

    def call_function(self, func: AcaciaExpr, args: ARGS_T,
                      keywords: KEYWORDS_T, location=None) -> AcaciaExpr:
        if not isinstance(func, AcaciaCallable):
            self.error_c(ErrorType.UNCALLABLE, expr_type=str(func.data_type))
        res, commands = func.call_withframe(args, keywords, location)
        self.current_file.extend(commands)
        return res

    def _get_inline_result(self, expect_type: Optional["DataType"]):
        result = self.ctx.inline_result
        if result is None:
            # didn't specify result
            if expect_type is None or expect_type.matches_cls(NoneDataType):
                result = NoneLiteral(self.compiler)
            else:
                self.error_c(ErrorType.NEVER_RESULT)
        else:
            got = result.data_type
            if (expect_type is not None) and (not expect_type.matches(got)):
                self.error_c(ErrorType.WRONG_RESULT_TYPE,
                            expect=str(expect_type), got=str(got))
        return result

    def call_inline_func(self, func: InlineFunction,
                         args: ARGS_T, keywords: KEYWORDS_T) -> CALLRET_T:
        # We visit the AST node every time an inline function is called
        file = cmds.MCFunctionFile()
        with self.set_ctx(func.context), self.new_ctx(), \
             self.set_mcfunc_file(file):
            self.ctx.new_scope()
            self.ctx.inline_result = None
            self.ctx.current_function = func
            self.ctx.function_state = FUNC_INLINE
            # Register args into scope
            arg2value = func.arg_handler.match(args, keywords)
            for arg, value in arg2value.items():
                port = func.arg_ports[arg]
                if port is FuncPortType.by_reference:
                    if not value.is_assignable():
                        self.error_c(ErrorType.CANT_REF_ARG, arg=arg)
                    self.register_symbol(arg, value)
                elif port is FuncPortType.by_value:
                    dt = value.data_type
                    if not isinstance(dt, Storable):
                        self.error_c(ErrorType.UNSUPPORTED_ARG_TYPE,
                                        arg=arg, arg_type=str(dt))
                    tmp = dt.new_var()
                    self.register_symbol(arg, tmp)
                    self.current_file.extend(value.export(tmp))
                else:
                    assert port is FuncPortType.const
                    if not isinstance(value, ConstExpr):
                        self.error_c(ErrorType.ARG_NOT_CONST, arg=arg)
                    self.register_symbol(arg, value)
            # Visit body
            file.write_debug("## Start of inline function")
            for stmt in func.node.body:
                self.visit(stmt)
            file.write_debug("## End of inline function")
            result = self._get_inline_result(func.result_type)
        return result, file.commands

    def ccall_const_func(self, func: AcaciaCTFunction,
                         arg2value: Dict[str, "CTExpr"]) -> CTObj:
        with self.set_ctx(func.context):
            ctexec = CTExecuter(self.ctx.scope, self, self.file_name)
            for arg, value in arg2value.items():
                if isinstance(value, CTObj):
                    value = CTObjPtr(value)
                ctexec.current_scope.set(arg, value)
            for stmt in func.node.body:
                ctexec.visittop(stmt)
            result = ctexec.result
        if result is None:
            result = NoneLiteral(self.compiler)
        if not func.result_type.is_typeof(result):
            # This function might be called by `CTExecuter` and
            # therefore the error location should be set by that.
            raise Error(
                ErrorType.WRONG_RESULT_TYPE,
                expect=func.result_type.name,
                got=abs(result).cdata_type.name
            )
        return result

    # subscript

    def visit_Subscript(self, node: Subscript):
        object_: AcaciaExpr = self.visit(node.object)
        getitem = self.attribute_of(object_, "__getitem__")
        if getitem is None:
            self.error_c(ErrorType.NO_GETITEM,
                         type_=str(object_.data_type))
        args = list(map(self.visit, node.subscripts))
        return self.call_function(
            getitem, args, {}, location=self.node_location(node)
        )
