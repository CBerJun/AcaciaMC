"""Builtin callable objects.

There are 5 types of functions:
- AcaciaFunction: functions that are written in Acacia
- InlineFunction: functions written in Acacia that
  are annotated with `inline`
- BinaryFunction: functions that are written in Python,
  which is usually a builtin function
- BoundMethod: methods that are bound to an entity
  and we are sure which implementation we are calling
  (e.g. entity A: def foo(): ...
        entity B extends A: def foo(): ...
        b = B()
        A@b.foo()  # Definitely A.foo called
  )
- BoundMethodDispatcher: methods that are bound to an
  entity and we are not sure which implementation
  we are calling.
  (e.g. entity A: def foo(): ...
        entity B extends A: def foo(): ...
        def bar(a: entity(A)):
            a.foo()  # Is it A.foo or B.foo?
  )
"""

__all__ = ['AcaciaFunction', 'InlineFunction', 'BinaryFunction',
           'BoundMethod', 'BoundMethodDispatcher']

from typing import List, Dict, Union, TYPE_CHECKING, Callable

from acaciamc.error import *
from .base import *
from .types import *
from .. import generator

if TYPE_CHECKING:
    from acaciamc.mccmdgen.generator import MCFunctionFile
    from .base import ARGS_T, KEYWORDS_T, CALLRET_T
    from .entity import _EntityBase
    from .entity_template import EntityTemplate

class AcaciaFunction(AcaciaExpr):
    def __init__(self, name: str, args: List[str],
                 arg_types: Dict[str, Type],
                 arg_defaults: Dict[str, Union[AcaciaExpr, None]],
                 returns: DataType, compiler):
        super().__init__(
            DataType.from_type_cls(FunctionType, compiler), compiler
        )
        self.name = name
        self.arg_handler = ArgumentHandler(args, arg_types, arg_defaults)
        # Create a `VarValue` for every args according to their types
        # and store them as dict at `self.arg_vars`.
        # Meanwhile, check whether arg types are supported.
        self.arg_vars: Dict[str, VarValue] = {}
        for arg in args:
            type_ = arg_types[arg]
            try:
                self.arg_vars[arg] = type_.new_var()
            except NotImplementedError:
                # type.new_var() is not implemented
                raise Error(ErrorType.UNSUPPORTED_ARG_TYPE,
                            arg=arg, arg_type=type_.name)
        # Allocate a var for result value
        self.result_var = returns.new_var()
        # `file`: the target file of function. When it is None,
        # the function is empty. It should be assigned by `Generator`.
        self.file: Union["MCFunctionFile", None] = None

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        res = []
        # Parse args
        args = self.arg_handler.match(args, keywords)
        # Assign argument values to `arg_vars`
        for arg, value in args.items():
            res.extend(value.export(self.arg_vars[arg]))
        # Call function
        if self.file is not None:
            res.append(self.file.call())
        # Store result
        return self.result_var, res

class InlineFunction(AcaciaExpr):
    def __init__(self, node, args, arg_types, arg_defaults,
                 returns: DataType, compiler):
        # We store the InlineFuncDef node directly
        super().__init__(
            DataType.from_type_cls(FunctionType, compiler), compiler
        )
        self.node = node
        self.name = node.name
        self.result_var = returns.new_var()
        self.arg_handler = ArgumentHandler(args, arg_types, arg_defaults)

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        cmds = self.compiler.current_generator.call_inline_func(
            self, args, keywords)
        return self.result_var, cmds

class BinaryFunction(AcaciaExpr):
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
                Union["CALLRET_T", AcaciaExpr]
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
        It should return any `AcaciaExpr` as the result value or a tuple
        (element 1 is result value, element 2 is list of strings
        representing commands).
        """
        super().__init__(
            DataType.from_type_cls(FunctionType, compiler), compiler
        )
        self.implementation = implementation

    def call(self, args, keywords: dict):
        self._calling_args = list(args)
        self._calling_keywords = keywords.copy()
        # Implementation needs to return tuple[AcaciaExpr, list[str]],
        # but we allow `list[str]` to be omitted.
        res = self.implementation(self.compiler, args, keywords)
        if isinstance(res, tuple):
            return res
        elif isinstance(res, AcaciaExpr):
            return res, []
        else:
            raise ValueError("Invalid return of binary func "
                             "implementation: {}".format(res))

METHODDEF_T = Union[AcaciaFunction, InlineFunction]

class BoundMethod(AcaciaExpr):
    def __init__(self, object_: "_EntityBase", method_name: str,
                 definition: METHODDEF_T, compiler):
        super().__init__(
            DataType.from_type_cls(FunctionType, compiler), compiler
        )
        self.name = method_name
        self.object = object_
        self.definition = definition

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        if isinstance(self.definition, AcaciaFunction):
            result, cmds = self.definition.call(args, keywords)
        elif isinstance(self.definition, InlineFunction):
            old_self = self.compiler.current_generator.self_value
            self.compiler.current_generator.self_value = self.object
            result, cmds = self.definition.call(args, keywords)
            self.compiler.current_generator.self_value = old_self
        # `BinaryFunction`s cannot be method implementation
        # because we are not sure about their result data type
        else:
            raise TypeError("Unexpected target function %r" % self.definition)
        return result, cmds

class BoundMethodDispatcher(AcaciaExpr):
    def __init__(self, object_: "_EntityBase", method_name: str,
                 result_var: VarValue, compiler):
        super().__init__(
            DataType.from_type_cls(FunctionType, compiler), compiler
        )
        self.name = method_name
        self.object = object_
        self.possible_implementations: \
            List[Tuple["EntityTemplate", BoundMethod]] = []
        self.files: List[Tuple["ARGS_T", "KEYWORDS_T", "MCFunctionFile"]] = []
        self.result_var = result_var

    def _give_implementation(
            self, args: "ARGS_T", keywords: "KEYWORDS_T",
            file: "MCFunctionFile",
            template: "EntityTemplate", bound_method: BoundMethod
        ):
        try:
            result, cmds = bound_method.call(args, keywords)
        except Error:
            if template is self.object.template:
                raise  # required function
            return
        cmds.extend(result.export(self.result_var))
        file.write_debug("# To implementation in %s" % template.name)
        file.extend(
            export_execute_subcommands(
                ["if entity @s[tag=%s]" % template.runtime_tag],
                main=cmd
            )
            for cmd in cmds
        )

    def add_implementation(self, template: "EntityTemplate",
                           definition: METHODDEF_T):
        if template.is_subtemplate_of(self.object.template):
            bound_method = BoundMethod(
                self.object, self.name, definition, self.compiler)
            self.possible_implementations.append((template, bound_method))
            for args, keywords, file in self.files:
                self._give_implementation(args, keywords,
                                          file, template, bound_method)

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        file = generator.MCFunctionFile()
        self.files.append((args, keywords, file))
        self.compiler.add_file(file)
        file.write_debug("## Method dispatcher for %s.%s()"
                         % (self.object.template.name, self.name))
        for template, bound_method in self.possible_implementations:
            self._give_implementation(args, keywords,
                                      file, template, bound_method)
        return self.result_var, [export_execute_subcommands(
            ["as %s" % self.object], main=file.call()
        )]
