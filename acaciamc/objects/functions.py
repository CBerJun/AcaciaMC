"""
Function objects.

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
      upcast(a, A).bar()  # BoundMethod: must be bar in A
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
- BinaryCTFunction: functions that are written in Python and available
  under const context and runtime context.
- BinaryCTOnlyFunction: functions that are written in Python and
  only available under const context.
- AcaciaCTFunction: functions written in Acacia that are annotated with
  `const`.
"""

__all__ = [
    # Type
    'FunctionDataType',
    # Expressions
    'AcaciaFunction', 'InlineFunction', 'BinaryFunction',
    'BoundMethod', 'BoundVirtualMethod', 'ConstructorFunction',
    'AcaciaCTFunction', 'BinaryCTFunction', 'BinaryCTOnlyFunction'
]

from abc import abstractmethod
from typing import (
    TYPE_CHECKING, List, Dict, Union, Callable, Tuple, Optional, Generic,
    TypeVar, Any
)

import acaciamc.mccmdgen.cmds as cmds
from acaciamc.ast import FuncPortType
from acaciamc.error import *
from acaciamc.localization import localize
from acaciamc.mccmdgen.ctexpr import (
    CTObj, CTObjPtr, CTDataType, CTExpr, CTCallable
)
from acaciamc.mccmdgen.datatype import DefaultDataType, Storable
from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.mcselector import MCSelector
from acaciamc.mccmdgen.utils import unreachable, InvalidOpError
from .entity import EntityReference
from .none import NoneLiteral

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.ast import InlineFuncData, ConstFuncData
    from acaciamc.mccmdgen.datatype import DataType
    from acaciamc.mccmdgen.generator import Generator, Context
    from .entity import _EntityBase, TaggedEntity
    from .entity_template import EntityTemplate

T = TypeVar("T")
DT = TypeVar("DT")
IT = TypeVar("IT")


class ArgumentHandler(Generic[IT, T, DT]):
    """
    A tool to match function arguments against a given definition.
    `IT`: input argument type
    `T`: the main argument type, used in output and type checking
    `DT`: the type of the data type, used in type checking
    `T` and `DT` should only accept non-None values.
    """

    def __init__(self, args: List[str], arg_types: Dict[str, Optional[DT]],
                 arg_defaults: Dict[str, Optional[T]]):
        """`args`, `arg_types` and `arg_defaults` decide the expected
        pattern.
        """
        self.args = args
        self.arg_types = arg_types
        self.arg_defaults = arg_defaults
        # Throw away arguments that have no default value in
        # `arg_defaults`.
        for arg, value in self.arg_defaults.copy().items():
            if value is None:
                del self.arg_defaults[arg]
        self.ARG_LEN = len(self.args)

    def preconvert(self, arg: str, value: IT) -> T:
        """
        Convert input arguments of `IT` type to `T` type.
        Can be omitted only if `IT` is same as `T`.
        """
        return value

    def type_check(self, arg: str, value: T, type_: DT) -> Optional[T]:
        """
        Must be implemented by subclasses to check if the `value` is of
        `type_` type. If this returns successfully with `None`, then the
        value is accepted. If this returns successfully with a value of
        `T` type, then that value is used instead as the argument value.
        If the type check fails, this should not return.
        """
        raise NotImplementedError

    def __type_check(self, arg: str, value: T, type_: Optional[DT]) -> T:
        if type_ is None:
            return value
        else:
            r = self.type_check(arg, value, type_)
            return value if r is None else r

    def match(self, args: List[IT], keywords: Dict[str, IT]) -> Dict[str, T]:
        """Match the expected pattern with given call arguments.
        Return a `dict` mapping names to argument value.
        """
        if len(args) > self.ARG_LEN:
            raise Error(ErrorType.TOO_MANY_ARGS)
        res = dict.fromkeys(self.args)
        # positioned
        for i, value in enumerate(args):
            arg = self.args[i]
            value = self.preconvert(arg, value)
            res[arg] = self.__type_check(arg, value, self.arg_types[arg])
        # keyword
        for arg, value in keywords.items():
            if arg not in self.args:
                raise Error(ErrorType.UNEXPECTED_KEYWORD_ARG, arg=arg)
            if res[arg] is not None:
                raise Error(ErrorType.ARG_MULTIPLE_VALUES, arg=arg)
            value = self.preconvert(arg, value)
            res[arg] = self.__type_check(arg, value, self.arg_types[arg])
        # if any args are missing use default if exists, else error
        for arg, value in res.copy().items():
            if value is None:
                if arg in self.arg_defaults:
                    res[arg] = self.arg_defaults[arg]
                else:
                    raise Error(ErrorType.MISSING_ARG, arg=arg)
        return res


class AcaciaArgHandler(ArgumentHandler[AcaciaExpr, AcaciaExpr, "DataType"]):
    def __init__(
            self, args: List[str],
            arg_types: Dict[str, Optional["DataType"]],
            arg_defaults: Dict[str, Optional[AcaciaExpr]],
            compiler: "Compiler"
    ):
        super().__init__(args, arg_types, arg_defaults)
        self.compiler = compiler

    def type_check(self, arg: str, value: AcaciaExpr, tp: "DataType"):
        if not tp.matches(value.data_type):
            # Try implicit type conversion
            try:
                v = value.implicitcast(tp, self.compiler)
            except InvalidOpError:
                raise Error(
                    ErrorType.WRONG_ARG_TYPE, arg=arg,
                    expect=str(tp), got=str(value.data_type)
                )
            else:
                return v


class FunctionDataType(DefaultDataType):
    name = 'function'


ctdt_function = CTDataType("function")


class AcaciaFunction(ConstExprCombined, AcaciaCallable):
    cdata_type = ctdt_function

    def __init__(self, name: str, args: List[str],
                 arg_types: Dict[str, "Storable"],
                 arg_defaults: Dict[str, Union[AcaciaExpr, None]],
                 returns: "Storable", compiler: "Compiler",
                 source=None):
        super().__init__(FunctionDataType())
        self.name = name
        self.result_type = returns
        self.arg_handler = AcaciaArgHandler(
            args, arg_types, arg_defaults, compiler
        )
        # Create a `VarValue` for every args according to their types
        # and store them as dict at `self.arg_vars`.
        self.arg_vars: Dict[str, VarValue] = {
            arg: arg_type.new_var(compiler)
            for arg, arg_type in arg_types.items()
        }
        # Allocate a var for result value
        self.result_var = returns.new_var(compiler)
        # `file`: the target file of function. When it is None,
        # the function is empty. It should be assigned by `Generator`.
        self.file: Union[cmds.MCFunctionFile, None] = None
        # For error hint
        if source is not None:
            self.source = source
        self.func_repr = self.name

    def call(self, args: ARGS_T, keywords: KEYWORDS_T, compiler) -> CALLRET_T:
        res = []
        # Parse args
        arguments = self.arg_handler.match(args, keywords)
        # Assign argument values to `arg_vars`
        for arg, value in arguments.items():
            res.extend(value.export(self.arg_vars[arg], compiler))
        # Call function
        if self.file is not None:
            res.append(cmds.InvokeFunction(self.file))
        # Make a copy of `result_var`
        result = self.result_type.new_var(compiler)
        res.extend(self.result_var.export(result, compiler))
        result.is_temporary = True
        return result, res


class InlineFunction(ConstExprCombined, AcaciaCallable):
    cdata_type = ctdt_function

    def __init__(self, name: str, node: "InlineFuncData",
                 args, arg_types, arg_defaults, arg_ports,
                 returns: "DataType", result_port: FuncPortType,
                 context: "Context", owner: "Generator",
                 source=None):
        super().__init__(FunctionDataType())
        # We store the InlineFuncData node directly
        self.node = node
        self.owner = owner
        self.context = context
        self.name = name
        self.result_type = returns
        self.result_port = result_port
        self.arg_handler = AcaciaArgHandler(
            args, arg_types, arg_defaults, owner.compiler
        )
        self.arg_ports = arg_ports
        # For error hint
        if source is not None:
            self.source = source
        self.func_repr = self.name

    def call(self, args: ARGS_T, keywords: KEYWORDS_T, compiler) -> CALLRET_T:
        return self.owner.call_inline_func(self, args, keywords)


def _handle_impl_res(res: Union[CALLRET_T, AcaciaExpr, None]):
    if isinstance(res, tuple):  # CALLRET_T
        return res
    elif isinstance(res, AcaciaExpr):
        return res, []
    elif res is None:
        return NoneLiteral(), []
    else:
        unreachable("Invalid return of binary func "
                    f"implementation: {res!r}")


class BinaryFunction(ConstExprCombined, AcaciaCallable):
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
    cdata_type = ctdt_function

    def __init__(
            self,
            implementation: Callable[
                ["Compiler", ARGS_T, KEYWORDS_T],
                Union[CALLRET_T, AcaciaExpr, None]
            ]
    ):
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
        super().__init__(FunctionDataType())
        self.implementation = implementation
        self.func_repr = localize("objects.function.binary")

    def call(self, args: ARGS_T, keywords: KEYWORDS_T, compiler) -> CALLRET_T:
        return _handle_impl_res(self.implementation(compiler, args, keywords))


class CTArgHandler(ArgumentHandler[
                       Union[CTExpr, AcaciaExpr], CTExpr, "CTDataType"
                   ]):
    def preconvert(self, arg: str, value: Union[CTExpr, AcaciaExpr]):
        if isinstance(value, AcaciaExpr):
            if not isinstance(value, ConstExpr):
                raise Error(ErrorType.ARG_NOT_CONST, arg=arg)
            value = value.to_ctexpr()
        return value

    def type_check(self, arg: str, value: CTExpr, dt: "CTDataType"):
        v = abs(value)
        if not dt.is_typeof(v):
            # Try implicit type conversion
            try:
                new_value = value.cimplicitcast(dt)
            except InvalidOpError:
                raise Error(ErrorType.WRONG_ARG_TYPE, arg=arg,
                            expect=dt.name, got=v.cdata_type.name)
            else:
                return new_value


class AcaciaCTFunction(ConstExprCombined, AcaciaCallable, CTCallable):
    cdata_type = ctdt_function

    def __init__(self, name: str, node: "ConstFuncData",
                 args, arg_types, arg_defaults,
                 returns: "CTDataType",
                 context: "Context", owner: "Generator",
                 source=None):
        super().__init__(FunctionDataType())
        self.node = node
        self.owner = owner
        self.context = context
        self.name = name
        self.result_type = returns
        self.arg_handler = CTArgHandler(args, arg_types, arg_defaults)
        # For error hint
        if source is not None:
            self.source = source
        self.func_repr = self.name

    def call(self, args: ARGS_T, keywords: KEYWORDS_T, compiler) -> CALLRET_T:
        arg2value = self.arg_handler.match(args, keywords)
        r = abs(self.owner.ccall_const_func(self, arg2value))
        try:
            return r.to_rt(), []
        except InvalidOpError:
            raise Error(ErrorType.NON_RT_RESULT, got=r.cdata_type.name)

    def ccall(self, args: List["CTObj"],
              keywords: Dict[str, "CTObj"], compiler):
        arg2value = self.arg_handler.match(args, keywords)
        return self.owner.ccall_const_func(self, arg2value)


class BinaryCTOnlyFunction(CTCallable):
    cdata_type = ctdt_function

    def __init__(
            self, impl: Callable[
                ["Compiler", List[CTExpr], Dict[str, CTExpr]],
                Union[None, CTExpr, ConstExpr]
            ],
            *args, **kwds
    ):
        super().__init__(*args, **kwds)
        self.impl = impl
        self.func_repr = localize("objects.function.binary")

    def ccall(self, args: List[CTExpr], keywords: Dict[str, CTExpr],
              compiler: "Compiler") -> CTExpr:
        res = self.impl(compiler, args, keywords)
        if res is None:
            return NoneLiteral()
        if isinstance(res, (CTObj, CTObjPtr)):
            return res
        if isinstance(res, ConstExpr):
            return res.to_ctexpr()
        unreachable("invalid return value from impl of"
                    f" BinaryCTOnlyFunction: {res!r}")


class BinaryCTFunction(BinaryCTOnlyFunction, ConstExprCombined,
                       AcaciaCallable):
    cdata_type = ctdt_function

    def __init__(
            self, impl: Callable[
                ["Compiler", List[Union[CTExpr, AcaciaExpr]],
                 Dict[str, Union[CTExpr, AcaciaExpr]]],
                Union[None, CTExpr, AcaciaExpr, CALLRET_T]
            ]
    ):
        super().__init__(impl, FunctionDataType())
        self.func_repr = localize("objects.function.binary")

    def call(self, args: ARGS_T, keywords: KEYWORDS_T, compiler) -> CALLRET_T:
        res = self.impl(compiler, args, keywords)
        if isinstance(res, (CTObj, CTObjPtr)):
            res = abs(res)
            try:
                return res.to_rt(), []
            except InvalidOpError:
                raise Error(ErrorType.NON_RT_RESULT, got=res.cdata_type.name)
        return _handle_impl_res(res)


METHODDEF_T = Union[AcaciaFunction, InlineFunction]


class _BoundMethod(ConstExprCombined, AcaciaCallable):
    """
    A method bound to an entity, but when called it does not set self
    var. Self var is set by `BoundMethod` and `BoundVirtualMethod`.
    """
    cdata_type = ctdt_function

    def __init__(self, object_: "_EntityBase", method_name: str,
                 definition: METHODDEF_T):
        super().__init__(FunctionDataType())
        self.name = method_name
        self.object = object_
        self.definition = definition
        self.is_inline = isinstance(definition, InlineFunction)
        self.func_repr = self.name
        self.source = self.definition.source

    def call(self, args: ARGS_T, keywords: KEYWORDS_T, compiler) -> CALLRET_T:
        if self.is_inline:
            assert isinstance(self.definition, InlineFunction), \
                "Unexpected target function %r" % self.definition
            # `EntityReference` is needed so that `self` is not
            # assignable.
            self.definition.context.self_value = \
                EntityReference.from_other(self.object)
        result, commands = self.definition.call(args, keywords, compiler)
        # `BinaryFunction`s cannot be method implementation
        # because we are not sure about their result data type
        if self.is_inline:
            # For gc...
            self.definition.context.self_value = None
        return result, commands


class BoundMethod(ConstExprCombined, AcaciaCallable):
    cdata_type = ctdt_function

    def __init__(self, object_: "_EntityBase", method_name: str,
                 definition: METHODDEF_T,
                 get_self_var: Optional[Callable[[], "TaggedEntity"]],
                 # Getter of self var is needed to prevent circular
                 # dependency: creating an entity requires binding
                 # methods, binding a method requires self var which is
                 # just an entity, and creating an entity ...
                 ):
        super().__init__(FunctionDataType())
        self.content = _BoundMethod(object_, method_name, definition)
        self.func_repr = self.content.func_repr
        self.source = self.content.source
        self.self_var_getter = get_self_var
        assert (get_self_var is None) == self.content.is_inline

    def call(self, args: ARGS_T, keywords: KEYWORDS_T, compiler) -> CALLRET_T:
        result, commands = self.content.call(args, keywords, compiler)
        if not self.content.is_inline:
            commands[:0] = self.content.object.export(
                self.self_var_getter(), compiler
            )
        return result, commands


class BoundVirtualMethod(ConstExprCombined, AcaciaCallable):
    cdata_type = ctdt_function

    def __init__(self, object_: "_EntityBase", method_name: str,
                 result_var: VarValue, compiler: "Compiler"):
        super().__init__(FunctionDataType())
        self.name = method_name
        self.object = object_
        self.impls: \
            Dict[METHODDEF_T, Tuple[
                _BoundMethod, List["EntityTemplate"],
                Optional[Callable[[], "TaggedEntity"]]
            ]] = {}
        self.files: \
            List[Tuple[ARGS_T, KEYWORDS_T, cmds.MCFunctionFile]] = []
        self.result_var = result_var
        self.func_repr = self.name
        compiler.before_finish(self._generate)

    def add_implementation(
            self, template: "EntityTemplate", definition: METHODDEF_T,
            get_self_var: Optional[Callable[[], "TaggedEntity"]]
    ):
        if definition in self.impls:
            _, templates, _ = self.impls[definition]
            templates.append(template)
        elif template.is_subtemplate_of(self.object.template):
            bound_method = _BoundMethod(self.object, self.name, definition)
            self.impls[definition] = (bound_method, [template], get_self_var)

    def call(self, args: ARGS_T, keywords: KEYWORDS_T, compiler) -> CALLRET_T:
        file = cmds.MCFunctionFile()
        self.files.append((args, keywords, file))
        compiler.add_file(file)
        return self.result_var, [
            cmds.Execute(
                [cmds.ExecuteEnv("as", self.object.to_str())],
                cmds.InvokeFunction(file)
            )
        ]

    def _generate(self, compiler: "Compiler"):
        def _call_bm(args: ARGS_T, keywords: KEYWORDS_T,
                     bm: _BoundMethod) -> CMDLIST_T:
            result, commands = bm.call_withframe(
                args, keywords, compiler,
                location=
                localize("objects.function.bvm.dispatcher") % self.name
            )
            commands.extend(result.export(self.result_var, compiler))
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
                for template in templates:
                    sel.scores(compiler.etemplate_id_scb,
                               f"!{template.runtime_id}")
                sel_s = sel.to_str()
                commands = _call_bm(args, keywords, impl)
                if not commands:
                    continue
                f = cmds.MCFunctionFile()
                compiler.add_file(f)
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


class ConstructorFunction(AcaciaCallable):
    def call(self, args: ARGS_T, keywords: KEYWORDS_T, compiler) -> CALLRET_T:
        dt, kwds = self.pre_initialize(args, keywords, compiler)
        instance = dt.new_var(compiler)
        commands = self.initialize(instance, compiler, **kwds)
        return instance, commands

    @abstractmethod
    def initialize(self, instance, compiler, **kwds) -> CMDLIST_T:
        """Initialize the `instance` and return commands to execute."""
        pass

    def pre_initialize(self, args: ARGS_T, keywords: KEYWORDS_T, compiler) \
            -> Tuple[Storable, Dict[str, Any]]:
        """
        Called before `initialize` to determine the type of instance and
        which arguments to pass to `initialize`.
        """
        try:
            dt = self.datatype_hook()
            if not isinstance(dt, Storable):
                raise InvalidOpError
        except InvalidOpError:
            raise NotImplementedError(
                'pre_initialize or datatype_hook must be implemented'
            )
        return dt, {"args": args, "keywords": keywords}
