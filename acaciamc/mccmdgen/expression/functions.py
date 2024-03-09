"""Builtin callable objects.

There are several types of functions:
- AcaciaFunction: functions that are written in Acacia
- InlineFunction: functions written in Acacia that are annotated with
  `inline`
- BinaryFunction: functions that are written in Python, which are
  usually builtin functions
- BoundMethod: methods that are bound to an entity and we are sure
  which implementation we are calling
- BoundVirtualMethod: virtual/override methods that are bound to an
  entity and we are not sure which implementation we are calling.
  Example:
    entity A:
      def foo():
        pass
      virtual def bar():
        pass
    entity B extends A:
      override def bar():
        pass
    def f(a: A):
      a.foo()  # BoundMethod: must be foo in A
      A@a.bar()  # BoundMethod: must be bar in A
      a.bar()  # BoundVirtualMethod: bar in A or B?
- ConstructorFunction: a function that produces a new object. This
  exists only for optimization purposes.
    # `Entity` is a constructor, so in this code:
    x := Entity()
    # there is no temporary entity used during the construction, but
    # one entity is created and directly bound to `x`.
    # Additionally, this code:
    x = Entity()
    # is optimized too, because `Entity` can reconstruct `x` and set it
    # to a new entity.
- BinaryCTFunction: functions that are written in Python and only
  available under const context.
- BinaryMaybeCTFunction: implements both BinaryFunction and
  BinaryCTFunction.
- AcaciaCTFunction: functions written in Acacia that are annotated with
  `const`.
"""

__all__ = [
    # Type
    'FunctionDataType',
    # Expressions
    'AcaciaFunction', 'InlineFunction', 'BinaryFunction',
    'BoundMethod', 'BoundVirtualMethod', 'ConstructorFunction',
    'BinaryCTFunction', 'BinaryMaybeCTFunction', 'AcaciaCTFunction',
]

from typing import List, Dict, Union, TYPE_CHECKING, Callable, Tuple, Optional
from abc import abstractmethod

from acaciamc.error import *
from acaciamc.mccmdgen.datatype import DefaultDataType, Storable
from acaciamc.ast import FuncPortType
from acaciamc.mccmdgen.mcselector import MCSelector
import acaciamc.mccmdgen.cmds as cmds
from .base import *
from .none import NoneLiteral

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.ast import InlineFuncDef, ConstFuncDef
    from acaciamc.mccmdgen.datatype import DataType
    from acaciamc.mccmdgen.generator import Generator, Context
    from .base import ARGS_T, KEYWORDS_T, CALLRET_T
    from .entity import _EntityBase, TaggedEntity
    from .entity_template import EntityTemplate

class FunctionDataType(DefaultDataType):
    name = 'function'

class AcaciaFunction(ConstExpr, AcaciaCallable):
    def __init__(self, name: str, args: List[str],
                 arg_types: Dict[str, "Storable"],
                 arg_defaults: Dict[str, Union[AcaciaExpr, None]],
                 returns: "Storable", compiler,
                 source=None):
        super().__init__(FunctionDataType(compiler), compiler)
        self.name = name
        self.result_type = returns
        self.arg_handler = ArgumentHandler(args, arg_types, arg_defaults)
        # Create a `VarValue` for every args according to their types
        # and store them as dict at `self.arg_vars`.
        self.arg_vars: Dict[str, VarValue] = {
            arg: arg_type.new_var() for arg, arg_type in arg_types.items()
        }
        # Allocate a var for result value
        self.result_var = returns.new_var()
        # `file`: the target file of function. When it is None,
        # the function is empty. It should be assigned by `Generator`.
        self.file: Union[cmds.MCFunctionFile, None] = None
        # For error hint
        if source is not None:
            self.source = source
        self.func_repr = self.name

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        res = []
        # Parse args
        arguments = self.arg_handler.match(args, keywords)
        # Assign argument values to `arg_vars`
        for arg, value in arguments.items():
            res.extend(value.export(self.arg_vars[arg]))
        # Call function
        if self.file is not None:
            res.append(cmds.InvokeFunction(self.file))
        # Make a copy of `result_var`
        result = self.result_type.new_var()
        res.extend(self.result_var.export(result))
        result.is_temporary = True
        return result, res

class InlineFunction(ConstExpr, AcaciaCallable):
    def __init__(self, node: "InlineFuncDef",
                 args, arg_types, arg_defaults, arg_ports,
                 returns: "DataType", result_port: FuncPortType,
                 context: "Context", owner: "Generator",
                 compiler, source=None):
        super().__init__(FunctionDataType(compiler), compiler)
        # We store the InlineFuncDef node directly
        self.node = node
        self.owner = owner
        self.context = context
        self.name = node.name
        self.result_type = returns
        self.result_port = result_port
        self.arg_handler = ArgumentHandler(args, arg_types, arg_defaults)
        self.arg_ports = arg_ports
        # For error hint
        if source is not None:
            self.source = source
        self.func_repr = self.name

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        return self.owner.call_inline_func(self, args, keywords)

def _bin_call(impl, compiler, args: ARGS_T, keywords: KEYWORDS_T) -> CALLRET_T:
    res = impl(compiler, args, keywords)
    if isinstance(res, tuple):  # CALLRET_T
        return res
    elif isinstance(res, AcaciaExpr):
        return res, []
    elif res is None:
        return NoneLiteral(compiler), []
    else:
        raise ValueError("Invalid return of binary func "
                         "implementation: {}".format(res))

def _bin_ccall(impl, compiler, args: ARGS_T, keywords: KEYWORDS_T) \
        -> ConstExpr:
    res = impl(compiler, args, keywords)
    if res is None:
        return NoneLiteral(compiler)
    assert isinstance(res, ConstExpr)
    return res

class BinaryFunction(ConstExpr, AcaciaCallable):
    """These are the functions that are written in Python,
    rather than `AcaciaFunction`s which are written in Acacia.
    The arguments passed to `AcaicaFunction` are *assigned* to local
    vars (AcaciaFunction.arg_vars) using commands, while arguments
    passed to `BinaryFunction` are directly handled in Python and no
    command will be generated for passing the arguments (similar to
    inline functions).
    As a result, the arguments can be "unstorable" -- argument of any
    type will be accepted. Also, the result value can be "unstorable"
    -- any type of result can be returned.
    """
    def __init__(
            self,
            implementation: Callable[
                ["Compiler", "ARGS_T", "KEYWORDS_T"],
                Union["CALLRET_T", AcaciaExpr, None]
            ],
            compiler):
        """implementation: it handles a call to this binary function.
        It should accept 3 arguments: compiler, args and keywords.
          compiler: the `Compiler` object
          args: list of positional arguments passed to this function
          keywords: dict that holds keyword arguments (keys are strings
          representing keyword name and values are argument values)
        NOTE Dealing with arguments can be annoying, BUT we provide an
        argument parsing tool called Axe (see acaciamc/tools/axe.py).
        It should return any `AcaciaExpr` as the result value, a tuple
        (element 1 is result value, element 2 is list of strings
        representing commands) or None (returns acacia None and writes
        no command).
        """
        super().__init__(FunctionDataType(compiler), compiler)
        self.implementation = implementation
        self.func_repr = "<binary function>"

    def call(self, args: ARGS_T, keywords: KEYWORDS_T) -> CALLRET_T:
        return _bin_call(self.implementation, self.compiler, args, keywords)

class BinaryCTFunction(CTCallable):
    def __init__(
        self, implementation: Callable[
            ["Compiler", "ARGS_T", "KEYWORDS_T"],
            Optional[ConstExpr]
        ],
        compiler
    ):
        super().__init__(FunctionDataType(compiler), compiler)
        self.implementation = implementation
        self.func_repr = "<binary function>"

    def ccall(self, args: ARGS_T, keywords: KEYWORDS_T) -> ConstExpr:
        return _bin_ccall(self.implementation, self.compiler, args, keywords)

class BinaryMaybeCTFunction(CTCallable, AcaciaCallable):
    def __init__(
        self,
        normal_impl: Callable[
            ["Compiler", "ARGS_T", "KEYWORDS_T"],
            Union["CALLRET_T", AcaciaExpr, None]
        ],
        const_impl: Callable[
            ["Compiler", "ARGS_T", "KEYWORDS_T"],
            Optional[ConstExpr]
        ],
        compiler
    ):
        super().__init__(FunctionDataType(compiler), compiler)
        self.normal_impl = normal_impl
        self.const_impl = const_impl
        self.func_repr = "<binary function>"

    def call(self, args: ARGS_T, keywords: KEYWORDS_T) -> CALLRET_T:
        return _bin_call(self.normal_impl, self.compiler, args, keywords)

    def ccall(self, args: ARGS_T, keywords: KEYWORDS_T) -> ConstExpr:
        return _bin_ccall(self.const_impl, self.compiler, args, keywords)

METHODDEF_T = Union[AcaciaFunction, InlineFunction]

class _BoundMethod(ConstExpr, AcaciaCallable):
    """
    A method bound to an entity, but when called it does not set self
    var. Self var is set by `BoundMethod` and `BoundVirtualMethod`.
    """
    def __init__(self, object_: "_EntityBase", method_name: str,
                 definition: METHODDEF_T, compiler):
        super().__init__(FunctionDataType(compiler), compiler)
        self.name = method_name
        self.object = object_
        self.definition = definition
        self.is_inline = isinstance(definition, InlineFunction)
        self.func_repr = self.name
        self.source = self.definition.source

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        if not self.is_inline:
            result, commands = self.definition.call(args, keywords)
        else:
            assert isinstance(self.definition, InlineFunction), \
                   "Unexpected target function %r" % self.definition
            self.definition.context.self_value = self.object
            result, commands = self.definition.call(args, keywords)
        # `BinaryFunction`s cannot be method implementation
        # because we are not sure about their result data type
        return result, commands

class BoundMethod(ConstExpr, AcaciaCallable):
    def __init__(self, object_: "_EntityBase", method_name: str,
                 definition: METHODDEF_T,
                 get_self_var: Optional[Callable[[], "TaggedEntity"]],
                 # Getter of self var is needed to prevent circular
                 # dependency: creating an entity requires binding
                 # methods, binding a method requires self var which is
                 # just an entity, and creating an entity ...
                 compiler):
        super().__init__(FunctionDataType(compiler), compiler)
        self.content = _BoundMethod(object_, method_name, definition, compiler)
        self.func_repr = self.content.func_repr
        self.source = self.content.source
        self.self_var_getter = get_self_var
        assert (get_self_var is None) == self.content.is_inline

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        result, commands = self.content.call(args, keywords)
        if not self.content.is_inline:
            commands[:0] = self.content.object.export(self.self_var_getter())
        return result, commands

class BoundVirtualMethod(ConstExpr, AcaciaCallable):
    def __init__(self, object_: "_EntityBase", method_name: str,
                 result_var: VarValue, compiler):
        super().__init__(FunctionDataType(compiler), compiler)
        self.name = method_name
        self.object = object_
        self.impls: \
            Dict[METHODDEF_T, Tuple[
                _BoundMethod, List["EntityTemplate"],
                Optional[Callable[[], "TaggedEntity"]]
            ]] = {}
        self.files: \
            List[Tuple["ARGS_T", "KEYWORDS_T", cmds.MCFunctionFile]] = []
        self.result_var = result_var
        self.func_repr = self.name
        self.compiler.before_finish(self._generate)

    def add_implementation(
        self, template: "EntityTemplate", definition: METHODDEF_T,
        get_self_var: Optional[Callable[[], "TaggedEntity"]]
    ):
        if definition in self.impls:
            _, templates, _ = self.impls[definition]
            templates.append(template)
        elif template.is_subtemplate_of(self.object.template):
            bound_method = _BoundMethod(
                self.object, self.name, definition, self.compiler
            )
            self.impls[definition] = (bound_method, [template], get_self_var)

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        file = cmds.MCFunctionFile()
        self.files.append((args, keywords, file))
        self.compiler.add_file(file)
        return self.result_var, [
            cmds.Execute(
                [cmds.ExecuteEnv("as", self.object.to_str())],
                cmds.InvokeFunction(file)
            )
        ]

    def _generate(self):
        def _call_bm(args: "ARGS_T", keywords: "KEYWORDS_T",
                     bm: _BoundMethod) -> CMDLIST_T:
            result, commands = bm.call_withframe(
                args, keywords,
                location="<dispatcher of virtual method %s>" % self.name
            )
            commands.extend(result.export(self.result_var))
            return commands

        if len(self.impls) == 1:
            only_bm, _, _getself = next(iter(self.impls.values()))
            only_selfvar = None if _getself is None else _getself()
        else:
            only_bm = only_selfvar = None
        for args, keywords, file in self.files:
            file.write_debug(
                "## Virtual method dispatcher for %s.%s()"
                % (self.object.template.name, self.name)
            )
            # Optimize: only one implementation
            if only_bm is not None:
                file.write_debug("# Only one implementation found")
                if only_selfvar is not None:
                    file.extend(only_selfvar.clear())
                    # XXX direct access to TaggedEntity.tag
                    file.write("tag @s add %s" % only_selfvar.tag)
                file.extend(_call_bm(args, keywords, only_bm))
                continue
            # Fallback
            for impl, (_, templates, get_self_var) in self.impls.items():
                file.write_debug(
                    "# For %s"
                    % (", ".join(template.name for template in templates))
                )
                sel = MCSelector("s")
                sel.tag_n(*[template.runtime_tag for template in templates])
                sel_s = sel.to_str()
                commands = _call_bm(args, keywords, impl)
                if not commands:
                    continue
                f = cmds.MCFunctionFile()
                self.compiler.add_file(f)
                f.write_debug("## Helper for virtual method dispatcher")
                f.extend(commands)
                if get_self_var is None:
                    file.write(cmds.Execute(
                        [
                            cmds.ExecuteCond("entity", sel_s, invert=True),
                            # Make sure @s is alive:
                            cmds.ExecuteCond("entity", "@s")
                        ],
                        runs=cmds.InvokeFunction(f)
                    ))
                else:
                    self_var = get_self_var()
                    # XXX direct access to TaggedEntity.tag
                    self_tag = self_var.tag
                    file.extend(self_var.clear())
                    file.write(cmds.Execute(
                        [cmds.ExecuteCond("entity", sel_s, invert=True)],
                        runs="tag @s add %s" % self_tag
                    ))
                    file.write(cmds.Execute(
                        [cmds.ExecuteCond("entity", "@s[tag=%s]" % self_tag)],
                        runs=cmds.InvokeFunction(f)
                    ))

class AcaciaCTFunction(CTCallable, AcaciaCallable):
    def __init__(self, node: "ConstFuncDef",
                 args, arg_types, arg_defaults,
                 returns: "DataType",
                 context: "Context", owner: "Generator",
                 compiler, source=None):
        super().__init__(FunctionDataType(compiler), compiler)
        self.node = node
        self.owner = owner
        self.context = context
        self.name = node.name
        self.result_type = returns
        self.arg_handler = ArgumentHandler(args, arg_types, arg_defaults)
        if source is not None:
            self.source = source
        self.func_repr = self.name

    def ccall(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> ConstExpr:
        return self.owner.call_const_func(self, args, keywords)

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        return self.owner.call_const_func(self, args, keywords), []

class ConstructorFunction(AcaciaCallable):
    # `initialize` should initialize a var of `var_type` type.
    # `var_type` defaults to call `datatype_hook` if it is implemented,
    # otherwise subclasses have to implement `var_type`.

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        instance = self.get_var_type().new_var()
        commands = self.initialize(instance, args, keywords)
        return instance, commands

    @abstractmethod
    def initialize(self, instance, args: "ARGS_T",
                   keywords: "KEYWORDS_T") -> CMDLIST_T:
        pass

    def get_var_type(self) -> Storable:
        if not hasattr(self, "_ctor_var_type"):
            self._ctor_var_type = self._var_type()
        return self._ctor_var_type

    def _var_type(self) -> Storable:
        return self.datatype_hook()
