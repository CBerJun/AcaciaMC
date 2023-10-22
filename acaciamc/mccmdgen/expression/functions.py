"""Builtin callable objects.

There are 5 types of functions:
- AcaciaFunction: functions that are written in Acacia
- InlineFunction: functions written in Acacia that
  are annotated with `inline`
- BinaryFunction: functions that are written in Python,
  which is usually a builtin function
- BoundMethod: methods that are bound to an entity
  and we are sure which implementation we are calling
- BoundMethodDispatcher: methods that are bound to an
  entity and we are not sure which implementation
  we are calling.
  Example:
    entity A:
      def foo():
        pass
      virtual def bar():
        pass
    entity B extends A:
      def bar():
        pass
    def f(a: entity(A)):
      a.foo()  # BoundMethod: must be foo in A
      A@a.bar()  # BoundMethod: must be bar in A
      a.bar()  # BoundMethodDispatcher: bar in A or B?
"""

__all__ = [
    # Type
    'FunctionDataType',
    # Expressions
    'AcaciaFunction', 'InlineFunction', 'BinaryFunction',
    'BoundMethod', 'BoundMethodDispatcher'
]

from typing import List, Dict, Union, TYPE_CHECKING, Callable, Tuple, Optional

from acaciamc.error import *
from acaciamc.mccmdgen.datatype import DefaultDataType, Storable
import acaciamc.mccmdgen.cmds as cmds
from .base import *
from .none import NoneVar

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.ast import InlineFuncDef
    from acaciamc.mccmdgen.datatype import DataType
    from .base import ARGS_T, KEYWORDS_T, CALLRET_T
    from .entity import _EntityBase
    from .entity_template import EntityTemplate

class FunctionDataType(DefaultDataType):
    name = 'function'

class AcaciaFunction(AcaciaCallable):
    def __init__(self, name: str, args: List[str],
                 arg_types: Dict[str, "Storable"],
                 arg_defaults: Dict[str, Union[AcaciaExpr, None]],
                 returns: "Storable", compiler,
                 source=None):
        super().__init__(FunctionDataType(), compiler)
        self.name = name
        self.result_type = returns
        self.arg_handler = ArgumentHandler(args, arg_types, arg_defaults)
        # Create a `VarValue` for every args according to their types
        # and store them as dict at `self.arg_vars`.
        # Meanwhile, check whether arg types are supported.
        self.arg_vars: Dict[str, VarValue] = {}
        for arg in args:
            self.arg_vars[arg] = arg_types[arg].new_var()
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
        return self.result_var, res

class InlineFunction(AcaciaCallable):
    def __init__(self, node: "InlineFuncDef", args, arg_types, arg_defaults,
                 returns: Optional["DataType"], compiler, source=None):
        super().__init__(FunctionDataType(), compiler)
        # We store the InlineFuncDef node directly
        self.node = node
        self.name = node.name
        self.result_type = returns
        self.arg_handler = ArgumentHandler(args, arg_types, arg_defaults)
        # For error hint
        if source is not None:
            self.source = source
        self.func_repr = self.name

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        return self.compiler.current_generator.call_inline_func(
            self, args, keywords
        )

class BinaryFunction(AcaciaCallable):
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
        super().__init__(FunctionDataType(), compiler)
        self.implementation = implementation
        self.func_repr = "<binary function>"

    def call(self, args: ARGS_T, keywords: KEYWORDS_T) -> CALLRET_T:
        res = self.implementation(self.compiler, args, keywords)
        if isinstance(res, tuple):  # CALLRET_T
            return res
        elif isinstance(res, AcaciaExpr):
            return res, []
        elif res is None:
            return NoneVar(self.compiler), []
        else:
            raise ValueError("Invalid return of binary func "
                             "implementation: {}".format(res))

METHODDEF_T = Union[AcaciaFunction, InlineFunction]

class _BoundMethod(AcaciaCallable):
    """
    A method bound to an entity, but when called it does not add
    /execute as (bound entity) run ...
    This exists to optimize in virtual method dispatchers. 
    Virtual method dispatchers are guaranteed to be executed "as" the
    entity which is bound to the dispatcher, so there is no need to say
    "as" again in the dispatcher.
    """
    def __init__(self, object_: "_EntityBase", method_name: str,
                 definition: METHODDEF_T, compiler):
        super().__init__(FunctionDataType(), compiler)
        self.name = method_name
        self.object = object_
        self.definition = definition
        self.func_repr = self.name
        self.source = self.definition.source

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        if isinstance(self.definition, AcaciaFunction):
            result, commands = self.definition.call(args, keywords)
        elif isinstance(self.definition, InlineFunction):
            old_self = self.compiler.current_generator.self_value
            self.compiler.current_generator.self_value = self.object
            result, commands = self.definition.call(args, keywords)
            self.compiler.current_generator.self_value = old_self
        # `BinaryFunction`s cannot be method implementation
        # because we are not sure about their result data type
        else:
            raise TypeError("Unexpected target function %r" % self.definition)
        return result, commands

class BoundMethod(AcaciaCallable):
    def __init__(self, object_: "_EntityBase", method_name: str,
                 definition: METHODDEF_T, compiler):
        super().__init__(FunctionDataType(), compiler)
        self.content = _BoundMethod(object_, method_name, definition, compiler)
        self.func_repr = self.content.func_repr
        self.source = self.content.source

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        result, commands = self.content.call(args, keywords)
        commands2 = [
            cmds.execute([
                cmds.ExecuteEnv("as", self.content.object.to_str())
            ], runs=cmd)
            for cmd in commands
        ]
        return result, commands2

class BoundMethodDispatcher(AcaciaCallable):
    def __init__(self, object_: "_EntityBase", method_name: str,
                 result_var: VarValue, compiler):
        super().__init__(FunctionDataType(), compiler)
        self.name = method_name
        self.object = object_
        self.possible_implementations: \
            List[Tuple["EntityTemplate", _BoundMethod]] = []
        self.files: \
            List[Tuple["ARGS_T", "KEYWORDS_T", cmds.MCFunctionFile]] = []
        self.result_var = result_var
        self.func_repr = self.name

    def _give_implementation(
            self, args: "ARGS_T", keywords: "KEYWORDS_T",
            file: cmds.MCFunctionFile,
            template: "EntityTemplate", bound_method: _BoundMethod
        ):
        result, commands = bound_method.call_withframe(
            args, keywords,
            location="<dispatcher of virtual method %s>" % self.name
        )
        commands.extend(result.export(self.result_var))
        file.write_debug("# To implementation in %s" % template.name)
        file.extend(
            cmds.execute(
                [cmds.ExecuteCond(
                    "entity", "@s[tag=%s]" % template.runtime_tag
                )], runs=cmd
            )
            for cmd in commands
        )

    def add_implementation(self, template: "EntityTemplate",
                           definition: METHODDEF_T):
        if template.is_subtemplate_of(self.object.template):
            bound_method = _BoundMethod(
                self.object, self.name, definition, self.compiler
            )
            self.possible_implementations.append((template, bound_method))
            for args, keywords, file in self.files:
                self._give_implementation(args, keywords,
                                          file, template, bound_method)

    def call(self, args: "ARGS_T", keywords: "KEYWORDS_T") -> "CALLRET_T":
        file = cmds.MCFunctionFile()
        self.files.append((args, keywords, file))
        self.compiler.add_file(file)
        file.write_debug("## Virtual method dispatcher for %s.%s()"
                         % (self.object.template.name, self.name))
        for template, bound_method in self.possible_implementations:
            self._give_implementation(args, keywords,
                                      file, template, bound_method)
        return self.result_var, [cmds.Execute(
            [cmds.ExecuteEnv("as", self.object.to_str())],
            runs=cmds.InvokeFunction(file)
        )]
