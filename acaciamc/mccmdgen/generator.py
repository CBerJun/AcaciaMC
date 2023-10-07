"""Minecraft Command Generator of Acacia."""

__all__ = ['Generator']

from typing import Union, TYPE_CHECKING, Optional, List, Tuple, Callable, Dict
import contextlib
import operator as builtin_op

from acaciamc.ast import *
from acaciamc.error import *
from acaciamc.mccmdgen.expression import *
from acaciamc.mccmdgen.symbol import ScopedSymbolTable
from acaciamc.mccmdgen.mcselector import MCSelector
from acaciamc.mccmdgen.datatype import Storable
import acaciamc.mccmdgen.cmds as cmds

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.datatype import DataType

FUNC_NONE = "none"
FUNC_INLINE = "inline"
FUNC_NORMAL = "normal"

class Generator(ASTVisitor):
    """Generates MC function from an AST for a single file."""
    def __init__(self, node: AST, main_file: cmds.MCFunctionFile,
                 compiler: "Compiler"):
        super().__init__()
        self.node = node
        self.compiler = compiler
        self.current_file = main_file
        self.current_scope = ScopedSymbolTable(builtins=self.compiler.builtins)
        # current_function: the current function we are visiting
        self.current_function = None
        # result_var_declared: whether result var is declared by user
        # only exists when visiting non-inline functions.
        self.result_var_declared: Optional[bool] = None
        # inline_result: stores result expression of inline function
        # only exists when visiting inline functions.
        self.inline_result = None
        # function_state: "none" | "inline" | "normal"
        # stores type of the nearest level of function. If not in any
        # function, it is "none".
        self.function_state = FUNC_NONE
        # self_value: the entity keyword `self` value
        self.self_value = None
        # processing_node: prepared for showing errors
        # to know which AST we are passing (so that lineno and col are known)
        self.processing_node = self.node
        self.node_depth = -1  # how deep we are in the tree (for debug comment)
        # current_tmp_scores: tmp scores allocated on current statement
        # see method `visit`.
        self.current_tmp_scores = []
        # current_tmp_entities: just like `current_tmp_scores`, but
        # store tmp `EntityVar`s.
        self.current_tmp_entities: List[Union[TaggedEntity, EntityGroup]] = []

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
        return AcaciaModule(self.current_scope, self.compiler)

    def fix_error_location(self, error: Error):
        error.set_location(self.processing_node.lineno,
                           self.processing_node.col)

    # --- INTERNAL USE ---

    def error_c(self, *args, **kwds):
        self.error(Error(*args, **kwds))

    def error(self, error: Error):
        if not error.location_set():
            self.fix_error_location(error)
        raise error

    def check_assignable(self, value: AcaciaExpr):
        """Raise error when an `AcaciaExpr` can't be assigned."""
        if not isinstance(value, VarValue):
            self.error_c(ErrorType.INVALID_ASSIGN_TARGET)

    def register_symbol(
            self, target_node: Union[Identifier, Attribute, Result],
            target_value: AcaciaExpr
        ):
        """Register a value to a symbol table according to AST.
        `target_value` is the value that the ast represents
        e.g. Identifier(name='a'), IntVar(...) ->
             self.current_scope.set('a', IntVar(...))
        """
        if isinstance(target_node, Identifier):
            self.current_scope.set(target_node.name, target_value)
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
            if self.function_state == FUNC_INLINE:
                self.inline_result = target_value
            elif self.function_state == FUNC_NORMAL:
                assert target_value is self.current_function.result_var
                self.result_var_declared = True
            else:
                assert self.function_state == FUNC_NONE
                self.error_c(ErrorType.RESULT_OUT_OF_SCOPE)
        else:
            raise TypeError

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
    def new_scope(self):
        """Create a new scope."""
        old = self.current_scope
        s = ScopedSymbolTable(outer=old, builtins=self.compiler.builtins)
        self.current_scope = s
        yield s
        self.current_scope = old

    @contextlib.contextmanager
    def set_func_state(self, state: str):
        old = self.function_state
        self.function_state = state
        yield
        self.function_state = old

    # --- VISITORS ---

    def visit(self, node: AST, **kwargs):
        # store which node we are passing now
        old_node = self.processing_node
        self.processing_node = node
        self.node_depth += 1  # used by `self.write_debug`
        if isinstance(node, Statement):
            # NOTE `current_tmp_scores` and `current_tmp_entities` are
            # modified by `Compiler`, to tell the tmp scores that are
            # allocated in this statement so that we can free them when
            # the statement ends.
            # Therefore, only update tmp scores when node is a
            # `Statement`.
            old_tmp_scores = self.current_tmp_scores
            self.current_tmp_scores = []
            old_tmp_entities = self.current_tmp_entities
            self.current_tmp_entities = []
        # write debug
        if not isinstance(node, (Expression, ArgumentTable,
                                 AnyTypeSpec, CallTable)):
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
            for entity in self.current_tmp_entities:
                self.current_file.extend(entity.clear())
            self.current_tmp_scores = old_tmp_scores
            self.current_tmp_entities = old_tmp_entities
        return res

    def visit_Module(self, node: Module):
        # start
        for stmt in node.body:
            self.visit(stmt)

    # --- STATEMENT VISITORS ---

    def visit_VarDef(self, node: VarDef):
        dt: Optional[DataType] = None
        value: Optional[AcaciaExpr] = None
        # Analyze data type
        if node.type is not None:
            dt = self.visit(node.type)
        if node.value is not None:
            value = self.visit(node.value)
            if dt is None:
                # Using x := z
                dt = value.data_type
            else:
                # Using x: y = z
                if not dt.is_type_of(value):
                    self.error_c(
                        ErrorType.WRONG_ASSIGN_TYPE,
                        got=str(value.data_type), expect=str(dt)
                    )
        # Create variable
        assert dt is not None
        if not isinstance(dt, Storable):
            self.error_c(ErrorType.UNSUPPORTED_VAR_TYPE, var_type=str(dt))
        if node.args is None:
            args, keywords = [], {}
        else:
            args, keywords = self.visit(node.args)
        is_result = isinstance(node.target, Result)
        if not (is_result and self.function_state == FUNC_NORMAL):
            var = dt.new_var()
        if is_result:
            if self.function_state == FUNC_NORMAL:
                assert isinstance(self.current_function, AcaciaFunction)
                var = self.current_function.result_var
            else:
                assert self.function_state == FUNC_INLINE
                assert var is not None
            result_type = self.current_function.result_type
            if (result_type is not None) and (not result_type.matches(dt)):
                self.error_c(ErrorType.WRONG_RESULT_TYPE,
                             expect=str(result_type), got=str(dt))
        _, cmds = dt.get_var_initializer(var).call(args, keywords)
        self.register_symbol(node.target, var)
        # Assign
        if value is not None:
            cmds.extend(value.export(var))
        # Write commands
        self.current_file.extend(cmds)

    def visit_Assign(self, node: Assign):
        # analyze expr first
        value = self.visit(node.value)
        # then analyze target
        target = self.visit(node.target)
        self.check_assignable(target)
        # check type
        if not target.data_type.matches(value.data_type):
            self.error_c(
                ErrorType.WRONG_ASSIGN_TYPE,
                expect=str(target.data_type), got=str(value.data_type)
            )
        # assign
        self.current_file.extend(value.export(target))

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
        # special check for result
        if isinstance(node.target, Result):
            if self.function_state != FUNC_INLINE:
                self.error_c(ErrorType.RESULT_BIND_OUT_OF_SCOPE)
        # analyze value
        value = self.visit(node.value)
        # register to symbol table
        self.register_symbol(node.target, value)

    def visit_ExprStatement(self, node: ExprStatement):
        self.visit(node.value)

    def visit_Pass(self, node: Pass):
        pass

    def visit_Command(self, node: Command):
        # get exact command (without formatting)
        cmd = ''
        for section in node.values:
            # expressions in commands need to be parsed
            if section[0] is StringMode.expression:
                expr_ast = section[1]
                expr = self.visit(expr_ast)
                try:
                    value = expr.cmdstr()
                except NotImplementedError:
                    err = Error(ErrorType.INVALID_CMD_FORMATTING)
                    err.set_location(expr_ast.lineno, expr_ast.col)
                    self.error(err)
                cmd += value
            elif section[0] is StringMode.text:
                cmd += section[1]
            else:
                raise ValueError
        command = cmds.Cmd(cmd, suppress_special_cmd=True)
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
        condition_var: BoolVar = BoolVar.new(self.compiler)
        dependencies: CMDLIST_T = condition.export(condition_var)
        self.current_file.extend(dependencies)
        # process body
        with self.new_mcfunc_file() as body_file:
            self.write_debug('If body')
            for stmt in node.body:
                self.visit(stmt)
        if body_file.has_content():
            # only add command when some commands ARE generated
            self.current_file.write(cmds.Execute(
                [cmds.ExecuteScoreMatch(condition_var.slot, "1")],
                runs=cmds.InvokeFunction(body_file)
            ))
        # process else_bosy (almost same as above)
        with self.new_mcfunc_file() as else_body_file:
            self.write_debug('Else branch of If')
            for stmt in node.else_body:
                self.visit(stmt)
        if else_body_file.has_content():
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
        # convert condition to BoolVar
        dependencies, condition = to_BoolVar(condition, tmp=False)
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
                    [cmds.ExecuteScoreMatch(condition.slot, "1")],
                    runs=cmds.InvokeFunction(body_file)
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

    def visit_EntityTypeSpec(self, node: EntityTypeSpec):
        if node.template is None:
            # When template is omitted, use builtin `Object` template
            template = self.compiler.base_template
        else:
            template = self.visit(node.template)
            if not template.data_type.matches_cls(ETemplateDataType):
                self.error_c(ErrorType.INVALID_ETEMPLATE,
                             got=str(template.data_type))
        return EntityDataType(template)

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
            returns=returns, compiler=self.compiler
        )

    @contextlib.contextmanager
    def _in_noninline_func(self, func: AcaciaFunction):
        old = self.current_function
        oldd = self.result_var_declared
        self.current_function = func
        self.result_var_declared = False
        with self.set_func_state(FUNC_NORMAL):
            yield
        # Check result var
        if (not self.result_var_declared
            and not func.result_type.matches_cls(NoneDataType)):
            self.error_c(ErrorType.NEVER_RESULT)
        # Resume
        self.current_function = old
        self.result_var_declared = oldd

    @contextlib.contextmanager
    def _in_inline_func(self, func: InlineFunction):
        old = self.current_function
        oldr = self.inline_result
        self.inline_result = None
        self.current_function = func
        with self.set_func_state(FUNC_INLINE):
            yield
        self.inline_result = oldr
        self.current_function = old

    def handle_inline_func(self, node: InlineFuncDef) -> InlineFunction:
        # Return the inline function object to a function definition
        if node.returns is None:
            returns = None
        else:
            returns = self.visit(node.returns)
        args, types, defaults = self.visit(node.arg_table)
        return InlineFunction(node, args, types, defaults,
                              returns, self.compiler)

    def visit_FuncDef(self, node: FuncDef):
        func = self._func_expr(node)
        with self.new_scope(), \
             self._in_noninline_func(func), \
             self.new_mcfunc_file() as body_file:
            # Register arguments to scope
            for arg, var in func.arg_vars.items():
                self.current_scope.set(arg, var)
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
        self.current_scope.set(node.name, func)
        return func

    def visit_InlineFuncDef(self, node: InlineFuncDef):
        func = self.handle_inline_func(node)
        self.current_scope.set(node.name, func)

    def _parse_module(self, meta: ModuleMeta):
        res = self.compiler.parse_module(meta)
        if isinstance(res, Error):
            self.error(res)
        return res

    def visit_Import(self, node: Import):
        module, path = self._parse_module(node.meta)
        self.write_debug("Got module from %s" % path)
        self.current_scope.set(node.name, module)

    def visit_FromImport(self, node: FromImport):
        module, path = self._parse_module(node.meta)
        self.write_debug("Import from %s" % path)
        for name, alias in node.id2name.items():
            value = module.attribute_table.lookup(name)
            if value is None:
                self.error_c(ErrorType.MODULE_NO_ATTRIBUTE,
                             attr=name, module=str(node.meta))
            self.current_scope.set(alias, value)

    def visit_FromImportAll(self, node: FromImportAll):
        module, path = self._parse_module(node.meta)
        self.write_debug("Import everything from %s" % path)
        for name, value in module.attribute_table:
            self.current_scope.set(name, value)

    def visit_EntityTemplateDef(self, node: EntityTemplateDef):
        field_types = {}  # Field name to `DataType`
        field_metas = {}  # Field name to field meta
        methods = {}  # Method name to function `AcaciaExpr`
        metas = {}  # Meta name to value
        # Handle parents
        parents = []
        for parent_ast in node.parents:
            parent = self.visit(parent_ast)
            if not parent.data_type.matches_cls(ETemplateDataType):
                self.error_c(ErrorType.INVALID_ETEMPLATE,
                             got=str(parent.data_type))
            parents.append(parent)
        # If parent is not specified, use builtin `Object`
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
                if isinstance(res, AcaciaFunction):
                    methods_2ndpass.append((res, decl.content))
            elif isinstance(decl, EntityMeta):
                # `res` is (mata name, mata value)
                key, value = res
                if key in metas:
                    self.error_c(ErrorType.REPEAT_ENTITY_META, meta=key)
                metas[key] = value
        # generate the template before 2nd pass, since `self` value
        # needs the template specified.
        template = EntityTemplate(node.name, field_types, field_metas,
                                  methods, parents, metas, self.compiler)
        # 2nd Pass: parse the non-inline method bodies.
        for method, ast in methods_2ndpass:
            with self.new_scope():
                # Register arguments to scope
                for arg, var in method.arg_vars.items():
                    self.current_scope.set(arg, var)
                # Handle `self`
                old_self = self.self_value
                self.self_value = EntityReference(
                    MCSelector("s"), template, self.compiler)
                # Write file
                with self.set_mcfunc_file(method.file), \
                     self._in_noninline_func(method):
                    self.write_debug('Entity method definition of %s.%s()' %
                                     (node.name, ast.name))
                    for stmt in ast.body:
                        self.visit(stmt)
                # Resume `self`
                self.self_value = old_self
        # Register
        self.current_scope.set(node.name, template)

    def visit_EntityField(self, node: EntityField):
        data_type = self.visit(node.type)
        try:
            field_meta = data_type.new_entity_field()
        except NotImplementedError:
            self.error_c(ErrorType.UNSUPPORTED_EFIELD_TYPE,
                         field_type=str(data_type))
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
        try:
            items = iterable.iterate()
        except NotImplementedError:
            raise Error(ErrorType.NOT_ITERABLE, type_=str(iterable.data_type))
        for value in items:
            with self.new_scope():
                self.current_scope.set(node.name, value)
                for stmt in node.body:
                    self.visit(stmt)

    def visit_ForEntity(self, node: ForEntity):
        egroup = self.visit(node.expr)
        if not egroup.data_type.matches_cls(EGroupDataType):
            self.error_c(ErrorType.INVALID_EGROUP, got=str(egroup.data_type))
        assert isinstance(egroup, EntityGroup)
        with self.new_mcfunc_file() as body_file, \
             self.new_scope():
            self.write_debug("For entity body")
            self.current_scope.set(
                node.name, EntityReference(
                    MCSelector("s"), egroup.template, self.compiler
                )
            )
            for stmt in node.body:
                self.visit(stmt)
        self.current_file.write(cmds.Execute(
            [cmds.ExecuteEnv("as", egroup.get_selector().to_str())],
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
        self.current_scope.set(node.name, StructTemplate(
            node.name, fields, base_structs, self.compiler
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
        elif isinstance(value, str):
            return String(value, self.compiler)
        elif value is None:
            return NoneLiteral(self.compiler)
        elif isinstance(value, float):
            return Float(value, self.compiler)
        raise TypeError

    def visit_Self(self, node: Self):
        v = self.self_value
        if v is None:
            self.error_c(ErrorType.SELF_OUT_OF_SCOPE)
        return v

    def visit_ArrayDef(self, node: ArrayDef):
        return Array(list(map(self.visit, node.items)), self.compiler)

    def visit_MapDef(self, node: MapDef):
        keys = list(map(self.visit, node.keys))
        values = list(map(self.visit, node.values))
        return Map(keys, values, self.compiler)

    # assignable

    def visit_Identifier(self, node: Identifier):
        res = self.current_scope.lookup(node.name)
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
        if not isinstance(selector, String):
            self.error_c(ErrorType.INVALID_RAWSCORE_SELECTOR,
                         got=str(selector.data_type))
        return IntVar(
            cmds.ScbSlot(selector.value, objective.value),
            compiler=self.compiler
        )

    def visit_Result(self, node: Result):
        if self.function_state == FUNC_NORMAL:
            if not self.result_var_declared:
                self.error_c(ErrorType.RESULT_UNDEFINED)
            return self.current_function.result_var
        elif self.function_state == FUNC_INLINE:
            if self.inline_result is None:
                self.error_c(ErrorType.RESULT_UNDEFINED)
            return self.inline_result
        else:
            assert self.function_state == FUNC_NONE
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
        if node.operator is Operator.positive:
            return self._wrap_op("unary +", builtin_op.pos, operand)
        elif node.operator is Operator.negative:
            return self._wrap_op("unary -", builtin_op.neg, operand)
        elif node.operator is Operator.not_:
            return self._wrap_method_op("not", "not_", operand)
        raise TypeError

    def visit_BinOp(self, node: BinOp):
        left, right = self.visit(node.left), self.visit(node.right)
        if node.operator is Operator.add:
            return self._wrap_op("+", builtin_op.add, left, right)
        elif node.operator is Operator.minus:
            return self._wrap_op("-", builtin_op.sub, left, right)
        elif node.operator is Operator.multiply:
            return self._wrap_op("*", builtin_op.mul, left, right)
        elif node.operator is Operator.divide:
            return self._wrap_op("/", builtin_op.floordiv, left, right)
        elif node.operator is Operator.mod:
            return self._wrap_op("%", builtin_op.mod, left, right)
        raise TypeError

    def visit_CompareOp(self, node: CompareOp):
        compares = []
        left, right = None, self.visit(node.left)
        # split `e0 o1 e1 o2 e2 ... o(n) e(n)` into
        # `e0 o1 e1 and ... and e(n-1) o(n) e(n)`
        for operand, operator in zip(node.operands, node.operators):
            left, right = right, self.visit(operand)
            compares.append(new_compare(left, operator, right, self.compiler))
        return new_and_group(compares, self.compiler)

    def visit_BoolOp(self, node: BoolOp):
        operands = [self.visit(operand) for operand in node.operands]
        if node.operator is Operator.and_:
            return new_and_group(operands, self.compiler)
        elif node.operator is Operator.or_:
            return new_or_expression(operands, self.compiler)
        raise TypeError

    # call

    def visit_Call(self, node: Call):
        # find called function
        func = self.visit(node.func)
        # call it
        res, cmds = func.call(*self.visit(node.table))
        # write commands
        self.current_file.extend(cmds)
        return res

    def call_inline_func(self, func: InlineFunction,
                         args: ARGS_T, keywords: KEYWORDS_T) -> CALLRET_T:
        # We visit the AST node every time an inline function is called
        # Return a list of commands
        with self.new_scope():
            # Register args directly into scope, without assigning
            # (as normal function calls do)
            arg2value = func.arg_handler.match(args, keywords)
            for arg, value in arg2value.items():
                self.current_scope.set(arg, value)
            # Visit body
            file = cmds.MCFunctionFile()
            with self.set_mcfunc_file(file), \
                 self._in_inline_func(func):
                self.write_debug("Start of inline function")
                for stmt in func.node.body:
                    self.visit(stmt)
                self.write_debug("End of inline function")
                result = self.inline_result
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
