# Generate commands of callable objects
from .base import *
from .types import *
from ...error import *

__all__ = ['AcaciaFunction', 'InlineFunction', 'BinaryFunction']

# There are 3 types of functions:
# - AcaciaFunction: functions that are written in Acacia
# - InlineFunction: functions written in Acacia that
#   are annotated with `inline`
# - BinaryFunction: functions that are written in Python,
#   which is usually a builtin function

class AcaciaFunction(AcaciaExpr):
    def __init__(
        self, args, arg_types, arg_defaults, returns: Type, compiler
    ):
        # args:list[str<an argument>]
        # types:dict{str<arg name>: Type<arg type>}
        # defaults:dict{str<arg name>: AcaciaExpr|None<default value>}
        # returns:Type Return type
        super().__init__(compiler.types[BuiltinFunctionType], compiler)
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
                 returns: Type, compiler):
        # We store the InlineFuncDef node directly
        super().__init__(compiler.types[BuiltinFunctionType], compiler)
        self.node = node
        self.result_var = returns.new_var()
        self.arg_handler = ArgumentHandler(
            args, arg_types, arg_defaults, compiler)
    
    def call(self, args, keywords: dict):
        self.compiler.current_generator.call_inline_func(self, args, keywords)
        return self.result_var, []

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
        super().__init__(compiler.types[BuiltinFunctionType], compiler)
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
        # type_:None|<subclass of Type>|tuple(<subclass of Type>)
        if type_ is None:
            return
        '''# check if `type_` is available
        if issubclass(type_, tuple):
            for t in type_:
                if not issubclass(t, Type):
                    raise TypeError
        elif not issubclass(type_, Type):
            raise TypeError'''
        if not isinstance(value.type, type_):
            if isinstance(type_, type) and issubclass(type_, Type):
                expect = type_.name
            else:
                expect = ', '.join(map(lambda t: t.name, type_))
            self.compiler.error(
                ErrorType.WRONG_ARG_TYPE, arg = arg,
                expect = expect, got = value.type.name
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
