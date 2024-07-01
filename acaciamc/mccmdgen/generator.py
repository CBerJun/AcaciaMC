"""Minecraft Command Generator of Acacia."""

__all__ = ['Generator', 'Context']

import contextlib
from typing import TYPE_CHECKING, Union, Optional, List, Tuple, Dict

import acaciamc.mccmdgen.cmds as cmds
from acaciamc.ast import *
from acaciamc.constants import FUNCTION_PATH_CHARS
from acaciamc.error import *
from acaciamc.localization import localize
from acaciamc.mccmdgen.ctexecuter import CTExecuter
from acaciamc.mccmdgen.ctexpr import CTObj, CTObjPtr
from acaciamc.mccmdgen.datatype import *
from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.mcselector import MCSelector
from acaciamc.mccmdgen.symbol import SymbolTable, CTRTConversionError
from acaciamc.mccmdgen.utils import unreachable, InvalidOpError
from acaciamc.objects import *
from acaciamc.objects.none import ctdt_none

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
    def __init__(self, scope: SymbolTable):
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
        # entity_new_data: used by entity `new` system
        self.entity_new_data: Optional[Tuple[AcaciaExpr, str]] = None

    def copy(self):
        res = Context(self.scope)
        res.current_function = self.current_function
        res.inline_result = self.inline_result
        res.function_state = self.function_state
        res.self_value = self.self_value
        res.entity_new_data = self.entity_new_data
        return res

    def new_scope(self):
        self.scope = SymbolTable(self.scope, self.scope.builtins)


class Generator(ASTVisitor):
    """Generates MC function from an AST for a single file."""

    def __init__(self, node: AST, main_file: cmds.MCFunctionFile,
                 file_name: str, compiler: "Compiler"):
        super().__init__()
        self.node = node
        self.compiler = compiler
        self.file_name = file_name
        self.current_file = main_file
        self.ctx = Context(SymbolTable(builtins=compiler.builtins))
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
        self.parse()
        return AcaciaModule(self.ctx.scope)

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
        var = dt.new_var(self.compiler)
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
            var = dt.new_var(self.compiler)
        else:
            var = value
        self.register_symbol(node.target, var)
        # Assign
        if value is not None and not is_ctor:
            self.current_file.extend(value.export(var, self.compiler))

    def _assign(self, target: AcaciaExpr, value_node: Expression):
        if not target.is_assignable():
            self.error_c(ErrorType.INVALID_ASSIGN_TARGET)
        value_type: Optional[DataType] = None
        value: Optional[AcaciaExpr] = None
        # analyze rvalue
        if isinstance(value_node, Call):
            func, table = self._call_inspect(value_node)
            if isinstance(func, ConstructorFunction):
                value_type, ctor_kwds = \
                    func.pre_initialize(*table, self.compiler)
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
        if value is not None:
            commands = value.export(target, self.compiler)
        else:
            commands = func.initialize(target, self.compiler, **ctor_kwds)
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
                commands = getattr(target, method)(value, self.compiler)
            except InvalidOpError:
                pass
            else:
                # Success
                self.current_file.extend(commands)
                return
        # Error
        self._op_error_s(localize(f"{node.operator.value}.augmented"),
                         target, value)

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
                expr: AcaciaExpr = self.visit(section)
                try:
                    value = expr.stringify()
                except InvalidOpError:
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
            new_cond = condition if has_then \
                else condition.unarynot(self.compiler)
            if isinstance(new_cond, SupportsAsExecute):
                # optimization for SupportsAsExecute (when only one of
                # then/else is present)
                dependencies, subcmds = new_cond.as_execute(self.compiler)
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
        dep, condition_var = to_BoolVar(condition, self.compiler, tmp=False)
        self.current_file.extend(dep)
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
            dep, subcmds = condition.as_execute(self.compiler)
        else:
            dep, cond_var = to_BoolVar(condition, self.compiler, tmp=False)
            subcmds = [cmds.ExecuteScoreMatch(cond_var.slot, "1")]
        # triggering the function
        if body_file.has_content():
            body_file.write_debug('## Part 2. Recursion')
            for file in (body_file, self.current_file):
                file.extend(dep)
                file.write(cmds.Execute(
                    subcmds, runs=cmds.InvokeFunction(body_file)
                ))
        else:
            self.write_debug('No commands generated')

    def visit_InterfaceDef(self, node: InterfaceDef):
        if isinstance(node.path, str):
            path = node.path
        else:
            s: String = self.visit(node.path)
            path = s.value
        # Make sure the path is valid
        if not path:
            self.error_c(ErrorType.INTERFACE_PATH_EMPTY)
        if path.startswith('/'):
            self.error_c(ErrorType.INTERFACE_PATH_SLASH_START)
        if path.endswith('/'):
            self.error_c(ErrorType.INTERFACE_PATH_SLASH_END)
        if '//' in path:
            self.error_c(ErrorType.INTERFACE_PATH_DOUBLE_SLASH)
        for c in path:
            if c not in FUNCTION_PATH_CHARS:
                self.error_c(ErrorType.INTERFACE_PATH_INVALID_CHAR, char=c)
        # Make sure the path is unique and not reserved
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
        except InvalidOpError:
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

    def _func_expr(self, fname: str, node: NormalFuncData) -> AcaciaFunction:
        """Return the function object to a function definition
        without parsing the body.
        """
        # get return type (of DataType type)
        if node.returns is None:
            returns = NoneDataType()
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
            name=fname, args=args, arg_types=types, arg_defaults=defaults,
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

    def visit_InlineFuncData(self, node: InlineFuncData, name: str) \
            -> InlineFunction:
        # Return the inline function object to a function definition
        if node.returns is None:
            returns = NoneDataType()
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
            name, node,
            args, arg_types, arg_defaults, arg_ports,
            returns, res_port, self.ctx.copy(), owner=self,
            source=self.node_location(node)
        )

    def visit_NormalFuncData(self, node: NormalFuncData, name: str) \
            -> AcaciaFunction:
        func = self._func_expr(name, node)
        with self._in_noninline_func(func), \
                self.new_mcfunc_file() as body_file:
            # Register arguments to scope
            for arg, var in func.arg_vars.items():
                self.register_symbol(arg, var)
            # Write file
            self.write_debug('Function definition of %s()' % name)
            for stmt in node.body:
                self.visit(stmt)
        # Add file
        if body_file.has_content():
            self.write_debug('Generated at %s' % body_file.get_path())
            func.file = body_file
        else:
            self.write_debug('No commands generated')
        return func

    def visit_ConstFuncData(self, node: ConstFuncData, name: str) \
            -> AcaciaCTFunction:
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
            name, node, args, arg_types, defaults,
            returns, self.ctx, owner=self,
            source=self.node_location(node)
        )

    def visit_FuncDef(self, node: FuncDef):
        func: AcaciaCallable = self.visit(node.data, name=node.name)
        func.source = self.node_location(node)
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

    def _method_body(
            self, method: AcaciaFunction, self_var: TaggedEntity,
            template_name: str, body: List[Statement]
    ):
        with self._in_noninline_func(method):
            # Set self
            self.ctx.self_value = self_var
            # Register arguments to scope
            for arg, var in method.arg_vars.items():
                self.register_symbol(arg, var)
            # Write commands
            with self.set_mcfunc_file(method.file):
                self.write_debug('Entity method definition of %s.%s()' %
                                 (template_name, method.name))
                for stmt in body:
                    self.visit(stmt)

    def visit_EntityTemplateDef(self, node: EntityTemplateDef):
        field_types = {}  # Field name to `DataType`
        field_metas = {}  # Field name to field meta
        methods = {}  # Method name to function `AcaciaExpr`
        method_qualifiers = {}  # Method name to qualifier
        method_new = (None if node.new_method is None
                      else self.visit(node.new_method))
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
        names_seen = set()

        def _name(node: AST, name: str):
            if name in names_seen:
                self.error_node(node, ErrorType.DUPLICATE_EFIELD, name=name)
            names_seen.add(name)

        for decl in node.body:
            res = self.visit(decl)
            if isinstance(decl, EntityField):
                # `res` is (field type, field meta)
                _name(decl, decl.name)
                field_types[decl.name], field_metas[decl.name] = res
            elif isinstance(decl, EntityMethod):
                # `res` is `AcaciaFunction`, `InlineFunction` or
                # `AcaciaCTFunction`
                _name(decl, decl.content.name)
                methods[decl.content.name] = res
                method_qualifiers[decl.content.name] = decl.qualifier
                if (
                        isinstance(res, AcaciaFunction)
                        and decl.qualifier is not MethodQualifier.static
                ):
                    methods_2ndpass.append((res, decl.content))
            else:
                assert isinstance(decl, Pass)
        # generate the template before 2nd pass, since `self` value
        # needs the template specified.
        template = EntityTemplate(
            node.name, field_types, field_metas,
            methods, method_qualifiers, method_new, parents,
            self.compiler, source=self.node_location(node)
        )
        # 2nd Pass: parse body of non-inline non-static methods.
        for method, ast in methods_2ndpass:
            if ast.name in template.method_dispatchers:
                disp = template.method_dispatchers[ast.name]
                _, gself = disp.impls[method]
                self_var = gself()
            else:
                assert ast.name in template.simple_methods
                self_var = template.simple_methods[ast.name].get_self_var()
            assert self_var is not None
            data = ast.data
            assert isinstance(data, NormalFuncData)
            # The self var getters will make sure the returned value is
            # not assignable, so no need to wrap it in `EntityReference`
            # here.
            self._method_body(method, self_var, node.name, data.body)
        # Also 2nd pass the `new` method if needed
        if isinstance(method_new, AcaciaNewFunction):
            nd_slot = method_new.template_id_var
            nd_tag = method_new.self_tag
            f = method_new.impl.file
            f.write_debug("## Clear tag used by `new` methods")
            f.write(f"tag @e[tag={nd_tag}] remove {nd_tag}")
            with self.new_ctx():
                self.ctx.entity_new_data = (IntVar(nd_slot), nd_tag)
                self_var = TaggedEntity(nd_tag, template)
                self_var.is_temporary = True
                self._method_body(
                    method_new.impl, self_var,
                    node.name, node.new_method.data.body
                )
        # Register
        self.register_symbol(node.name, template)

    def visit_EntityField(self, node: EntityField):
        data_type = self.visit(node.type)
        if not isinstance(data_type, SupportsEntityField):
            self.error_c(ErrorType.UNSUPPORTED_EFIELD_TYPE,
                         field_type=str(data_type))
        field_meta = data_type.new_entity_field(self.compiler)
        return data_type, field_meta

    def visit_EntityMethod(self, node: EntityMethod):
        data = node.content.data
        name = node.content.name
        if (isinstance(data, NormalFuncData)
                and node.qualifier is not MethodQualifier.static):
            func = self._func_expr(name, data)
            # Give this function a file
            file = cmds.MCFunctionFile()
            func.file = file
            self.compiler.add_file(file)
        else:
            func = self.visit(data, name=name)
        func.source = self.node_location(node)
        return func

    def visit_NewMethod(self, node: NewMethod):
        d = node.data
        inline = isinstance(d, InlineFuncData)
        if inline:
            func = self.visit(d, name="<new>")
        else:
            func = self._func_expr("<new>", d)
            if not func.result_type.matches_cls(NoneDataType):
                self.error_c(ErrorType.ENTITY_NEW_RETURN_TYPE,
                             got=func.result_type)
            # Give this function a file
            file = cmds.MCFunctionFile()
            func.file = file
            self.compiler.add_file(file)
        func.source = self.node_location(node)
        if not inline:
            # Allocate data needed by `new` system
            nd_slot = self.compiler.allocate()
            nd_tag = self.compiler.allocate_entity_tag()
            func = AcaciaNewFunction(func, nd_tag, nd_slot)
        return func

    def visit_For(self, node: For):
        iterable = self.visit(node.expr)
        # for-in on an entity group has completely different meaning --
        # it is not a compile-time loop.
        if not iterable.data_type.matches_cls(EGroupDataType):
            try:
                items = iterable.iterate()
            except InvalidOpError:
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
                executer = EntityReference(MCSelector("s"), iterable.template)
                self.current_file.extend(executer.export(this, self.compiler))
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
            node.name, fields, base_structs,
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
                if isinstance(func, ConstructorFunction):
                    value = None
                else:
                    value = self._call_invoke(node.value, func, table)
            else:
                value = self.visit(node.value)
            rv = self.ctx.current_function.result_var
            if value is None:
                dt, kwds = func.pre_initialize(*table, self.compiler)
                _check(dt)
                commands = func.initialize(rv, self.compiler, **kwds)
            else:
                _check(value.data_type)
                commands = value.export(rv, self.compiler)
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
                    self.ctx.inline_result = dt.new_var(self.compiler)
                    self.ctx.inline_result.is_temporary = True
                self.current_file.extend(
                    value.export(self.ctx.inline_result, self.compiler)
                )
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

    def visit_NewCall(self, node: NewCall):
        if self.ctx.entity_new_data is None:
            self.error_c(ErrorType.NEW_OUT_OF_SCOPE)
        if node.primary is None:
            primary = self.compiler.base_template
        else:
            primary: AcaciaExpr = self.visit(node.primary)
            if not isinstance(primary, EntityTemplate):
                self.error_c(ErrorType.INVALID_ETEMPLATE,
                             got=primary.data_type)
        args, keywords = self.visit(node.call_table)
        try:
            commands = primary.method_new(
                self.compiler, *self.ctx.entity_new_data, args, keywords
            )
        except Error as err:
            s = primary.method_new_source
            err.add_frame(ErrFrame(
                self.node_location(node),
                localize("generator.visit.newcall.tracemsg") % primary.name,
                note=None if s is None else
                localize("generator.visit.newcall.tracenote") % s
            ))
            raise
        self.current_file.extend(commands)

    # --- EXPRESSION VISITORS ---
    # literal

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
        return String(self.visit(node.content))

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
        return AcaciaList(self._ct_list(node.items))

    def visit_MapDef(self, node: MapDef):
        return Map(self._ct_list(node.keys),
                   self._ct_list(node.values))

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
        self._op_error_s(operator.localized, *operands)

    def visit_UnaryOp(self, node: UnaryOp):
        operand = self.visit(node.operand)
        try:
            res = getattr(operand, OP2METHOD[node.operator])(self.compiler)
        except InvalidOpError:
            self._op_error(node.operator, operand)
        return res

    def visit_BinOp(self, node: BinOp):
        left, right = self.visit(node.left), self.visit(node.right)
        meth = OP2METHOD[node.operator]
        try:
            res = getattr(left, meth)(right, self.compiler)
        except InvalidOpError:
            try:
                res = getattr(right, f"r{meth}")(left, self.compiler)
            except InvalidOpError:
                self._op_error(node.operator, left, right)
        return res

    def visit_CompareOp(self, node: CompareOp):
        compares = []
        left, right = None, self.visit(node.left)
        # split `e0 o1 e1 o2 e2 ... o(n) e(n)` into
        # `e0 o1 e1 and ... and e(n-1) o(n) e(n)`
        for operand, operator in zip(node.operands, node.operators):
            left, right = right, self.visit(operand)
            try:
                res = left.compare(operator, right, self.compiler)
            except InvalidOpError:
                try:
                    res = right.compare(
                        COMPOP_SWAP[operator], left, self.compiler
                    )
                except InvalidOpError:
                    self.error_c(
                        ErrorType.INVALID_OPERAND,
                        operator=operator.localized,
                        operand=f'"{left.data_type}", "{right.data_type}"'
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
                    operator=operator.localized,
                    operand=str(operand.data_type)
                )
        # Go
        if operator is Operator.and_:
            return new_and_group(operands, self.compiler)
        elif operator is Operator.or_:
            return new_or_expression(operands, self.compiler)
        unreachable()

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
            *table, self.compiler,
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
        res, commands = func.call_withframe(
            args, keywords, self.compiler, location
        )
        self.current_file.extend(commands)
        return res

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
                    tmp = dt.new_var(self.compiler)
                    self.register_symbol(arg, tmp)
                    self.current_file.extend(value.export(tmp, self.compiler))
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
            result = self.ctx.inline_result
            rt = func.result_type
            if result is None:
                # didn't specify result
                if rt is None or rt.matches_cls(NoneDataType):
                    result = NoneLiteral()
                else:
                    self.error_c(ErrorType.NEVER_RESULT)
            else:
                got = result.data_type
                if (rt is not None) and (not rt.matches(got)):
                    self.error_c(ErrorType.WRONG_RESULT_TYPE,
                                 expect=str(rt), got=str(got))
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
            result = NoneLiteral()
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
