# Generate commands of callable objects
from .base import *
from .types import *
from ...error import *
from .. import generator

__all__ = ['AcaciaFunction', 'InlineFunction', 'BinaryFunction',
           'BoundMethod', 'BoundMethodDispatcher']

# There are 5 types of functions:
# - AcaciaFunction: functions that are written in Acacia
# - InlineFunction: functions written in Acacia that
#   are annotated with `inline`
# - BinaryFunction: functions that are written in Python,
#   which is usually a builtin function
# - BoundMethod: methods that are bound to an entity
#   and we are sure which implementation we are calling
#   (e.g. entity A: def foo(): ...
#         entity B extends A: def foo(): ...
#         b = B()
#         A@b.foo()  # Definitely A.foo called
#   )
# - BoundMethodDispatcher: methods that are bound to an
#   entity and we are not sure which implementation
#   we are calling.
#   (e.g. entity A: def foo(): ...
#         entity B extends A: def foo(): ...
#         def bar(a: entity(A)):
#             a.foo()  # Is it A.foo or B.foo?
#   )

class AcaciaFunction(AcaciaExpr):
    def __init__(self, name: str, args, arg_types, arg_defaults,
                 returns: DataType, compiler):
        # args:list[str<an argument>]
        # types:dict{str<arg name>: Type<arg type>}
        # defaults:dict{str<arg name>: AcaciaExpr|None<default value>}
        # returns:Type Return type
        super().__init__(
            DataType.from_type_cls(FunctionType, compiler), compiler
        )
        self.name = name
        self.arg_handler = ArgumentHandler(
            args, arg_types, arg_defaults, self.compiler)
        # create a VarValue for every args according to their types
        # and store them as dict at self.arg_vars
        # meanwhile, check whether arg types are supported
        self.arg_vars = {} # str<arg name>:VarValue<place to store the arg>
        for arg in args:
            type_ = arg_types[arg]
            try:
                self.arg_vars[arg] = type_.new_var()
            except NotImplementedError:
                # type.new_var() is not implemented
                self.compiler.error(
                    ErrorType.UNSUPPORTED_ARG_TYPE,
                    arg = arg, arg_type = type_.name
                )
        # allocate a var for result value
        self.result_var = returns.new_var()
        # file:MCFunctionFile the target file of function
        # when it is None, meaning empty function;
        # it should be completed by Generator
        self.file = None
    
    def call(self, args, keywords: dict):
        # call the function with given `args` and `keywords`
        # args:iterable[AcaciaExpr] Positioned args
        # keywords:dict{str<arg>:AcaciaExpr} Keyword args
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
        self.arg_handler = ArgumentHandler(
            args, arg_types, arg_defaults, compiler)

    def call(self, args, keywords: dict):
        cmds = self.compiler.current_generator.call_inline_func(
            self, args, keywords)
        return self.result_var, cmds

class BinaryFunction(AcaciaExpr):
    # These are the functions that are written in Python,
    # rather than AcaciaFunction which is written in Acacia
    # The args passed to AcaicaFunction are assigned to local vars
    # (AcaciaFunction.arg_vars) using commands; but args passed to
    # BinaryFunction is directly handled in Python and no commands
    # will be generated for parsing the args
    # Therefore, the args are not static anymore -- Any args of any type
    # will be accepted; if the implementation of function is not satisfied
    # with the args given, it can raise an INVALID_BINARY_FUNC_ARG error
    # Also, the result value is not static -- Any types of result can be
    # returned.
    def __init__(self, implementation, compiler):
        # implementation: it should handle a call to this function,
        # and this BinaryFunction object is passed as its first argument.
        # The implementation should then parse the arguments using the
        # methods in this class (such as `arg_require`). At last, it needs
        # to give a result which could be any `AcaciaExpr`
        super().__init__(
            DataType.from_type_cls(FunctionType, compiler), compiler
        )
        self.implementation = implementation
    
    def call(self, args, keywords: dict):
        self._calling_args = list(args)
        self._calling_keywords = keywords.copy()
        # We need to return tuple[AcaciaExpr, list[str]],
        # but we allow binary function implementation to only return 1
        # `AcaciaExpr` as the result, omitting the commands to run
        res = self.implementation(self)
        if isinstance(res, tuple):
            return res
        elif isinstance(res, AcaciaExpr):
            return res, []
        else:
            raise ValueError("Invalid return of binary func implementation")
    
    # these are utils for implementation to parse arg more easily
    # the `type_` args are optional to check the type of args
    # it can be a Type or a tuple of Type
    
    def _check_arg_type(self, arg: str, value: AcaciaExpr, type_):
        # check type of arg
        # type_:None|<subclass of Type>|tuple(<subclass of Type>)|
        #       DataType|tuple(DataType)
        if type_ is None:
            return
        # Convert Type to DataType
        if isinstance(type_, type) and issubclass(type_, Type):
            type_ = DataType.from_type_cls(type_, self.compiler)
        # Make `type_` a tuple
        if isinstance(type_, tuple):
            nt = []
            for t in type_:
                if issubclass(t, Type):
                    nt.append(DataType.from_type_cls(t, self.compiler))
                else:
                    nt.append(t)
            type_ = tuple(nt)
        else:
            type_ = (type_,)
        if not any(map(lambda dt: dt.is_type_of(value), type_)):
            # If all the DataType can't match the `value`, raise error
            self.compiler.error(
                ErrorType.WRONG_ARG_TYPE, arg=arg,
                expect=', '.join(map(str, type_)), got=str(value.data_type)
            )
    
    def _find_arg(self, name: str) -> AcaciaExpr:
        # find the given arg and return its value
        # if not found, return None
        res1, res2 = None, None
        ## find it in positioned args
        if self._calling_args:
            res1 = self._calling_args.pop(0)
        ## find it in keyword
        if name in self._calling_keywords:
            res2 = self._calling_keywords.pop(name)
        ## decide result
        if res1 is None and res2 is None:
            return None
        if res1 is not None and res2 is not None:
            self.compiler.error(ErrorType.ARG_MULTIPLE_VALUES, arg = name)
        res = res2 if res1 is None else res1
        return res
    
    def arg_raw(self):
        # get all raw args
        res = (self._calling_args.copy(), self._calling_keywords.copy())
        self._calling_args.clear()
        self._calling_keywords.clear()
        return res

    def arg_require(self, name: str, type_ = None):
        # get a required argument of name `name`
        res = self._find_arg(name)
        ## check
        if res is None:
            self.compiler.error(ErrorType.MISSING_ARG, arg = name)
        self._check_arg_type(name, res, type_)
        return res
    
    def arg_optional(self, name: str, default: AcaciaExpr, type_ = None):
        # get an optional argument with default value
        res = self._find_arg(name)
        ## check
        if res is None:
            res = default
        self._check_arg_type(name, res, type_)
        return res
    
    def assert_no_arg(self):
        # assert there is no args left
        if bool(self._calling_args):
            self.compiler.error(ErrorType.TOO_MANY_ARGS)
        if bool(self._calling_keywords):
            self.compiler.error(
                ErrorType.UNEXPECTED_KEYWORD_ARG,
                arg = ', '.join(self._calling_keywords.keys())
            )
    
    # util for raising error

    def arg_error(self, arg: str, message: str):
        self.compiler.error(
            ErrorType.INVALID_BIN_FUNC_ARG,
            arg = arg, message = message
        )

class BoundMethod(AcaciaExpr):
    def __init__(self, object_: AcaciaExpr, method_name: str,
                 definition: AcaciaExpr, compiler):
        super().__init__(
            DataType.from_type_cls(FunctionType, compiler), compiler
        )
        self.name = method_name
        self.object = object_
        self.definition = definition

    def call(self, args, keywords):
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
    def __init__(self, object_: AcaciaExpr, method_name: str,
                 result_var: VarValue, compiler):
        super().__init__(
            DataType.from_type_cls(FunctionType, compiler), compiler
        )
        self.name = method_name
        self.object = object_
        # possible_implementations: list[tuple[<template>, BoundMethod]]
        self.possible_implementations = []
        # files: list[tuple[<args>, <keywords>, <file>]]
        self.files = []
        self.result_var = result_var

    def _give_implementation(
            self, args, keywords: dict,
            file: "generator.MCFunctionFile",
            template: AcaciaExpr, bound_method: BoundMethod
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

    def add_implementation(self, template, definition: AcaciaExpr):
        if template.is_subtemplate_of(self.object.template):
            bound_method = BoundMethod(
                self.object, self.name, definition, self.compiler)
            self.possible_implementations.append((template, bound_method))
            for args, keywords, file in self.files:
                self._give_implementation(args, keywords,
                                          file, template, bound_method)

    def call(self, args, keywords):
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
