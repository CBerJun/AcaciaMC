# Base things for generating codes of Acacia expressions
# Including base classes, simple types of expressions and utils

from ..symbol import AttributeTable
from ...error import *

__all__ = [
    # Utils
    'export_execute_subcommands', 'ArgumentHandler',
    # Base class
    'AcaciaExpr', 'VarValue', 'CallResult'
]

### --- UTILS --- ###

def export_execute_subcommands(subcmds: list, main: str) -> str:
    # convert a list of /execute subcommands into a command
    # e.g. cmds = ['if xxx', 'as xxx'], main = 'say ...'
    #  returns: 'execute if xxx as xxx run say ...'
    if not bool(subcmds):
        # optimization: if no subcommand given
        return main
    return 'execute ' + ' '.join(subcmds) + ' run ' + main

def _operator_class(cls):
    # class decorator that do the following things to operator methods:
    # ("operator methods" can be seen below in `OP2SHOW_NAME`)
    # This is used by AcaciaExpr only
    # - when it is defined, TypeError that it raised will be caught
    #   and do self.compiler.error(...) instead
    # - when it is undefined, define it and it will directly run
    #   self.compiler.error

    # create dict of decorated method names and the operator they represents
    OP2SHOW_NAME = {
        # unary
        '__pos__': 'unary +',
        '__neg__': 'unary -',
        'not_': 'not',
        # binary
        '__add__': '+',
        '__sub__': '-',
        '__mul__': '*',
        '__floordiv__': '/',
        '__mod__': '%',
        # don't forget __rxxx__ methods
        '__radd__': '+',
        '__rsub__': '-',
        '__rmul__': '*',
        '__rfloordiv__': '/',
        '__rmod__': '%',
        # augmented assign
        'iadd': '+=',
        'isub': '-=',
        'imul': '*=',
        'idiv': '/=',
        'imod': '%=',
    }
    # _handle: decorate the `func`, when error occured
    # use `show_name` (of operator) to complete error message
    def _handle(func, show_name):
        def _error(self, *args, **kwargs):
            self.compiler.error(
                ErrorType.INVALID_OPERAND,
                operator = show_name,
                operand = ', '.join(
                    repr(x.type.name) \
                    for x in (self, ) + args + tuple(kwargs.values())
                )
            )
        def _new(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except TypeError:
                _error(self, *args, **kwargs)
        
        if func is None:
            # for undefined ones, just run error
            return _error
        return _new
    # START
    for name, show_name in OP2SHOW_NAME.items():
        old = getattr(cls, name, None)
        setattr(cls, name, _handle(old, show_name))
    return cls

### --- END UTILS --- ###

# Decorate all the subclasses of AcaciaExpr with _operator_class
class _AcaciaExprMeta(type):
    def __new__(cls, *args, **kwargs):
        cls_instance = super().__new__(cls, *args, **kwargs)
        cls_instance._init_class()
        # _operator_class changes the operator methods;
        # so call method `_init_class` before decorating
        # to do some initializations
        return _operator_class(cls_instance)

class AcaciaExpr(metaclass=_AcaciaExprMeta):
    # Base class for EVERYTHING that represents an Acacia expression
    # An AcaciaExpr knows the value and provides interfaces to change it
    # !!! VERY IMPORTANT FOR CONTRIBUTORS !!!
    # NOTE There are 2 types of Acacia data types:
    # - The "storable" types. These types of expressions are stored in
    #   Minecraft, and their values can be changed when running the code
    #   (Since it is stored in MC)
    #   e.g. int, bool
    # - The "unstorable" types. These types of expression cannot be stored
    #   in Minecraft, and is only remembered by the compiler. Therefore,
    #   their values can't be changed.
    #   e.g. str, module, function
    # To define a new type, you need to:
    #  - Define a subclass of `Type` that represents the type
    #    The `name` (str) attribute must be given to show the name of your type
    #    please notice not to use `Type.__init__` for initializations!
    #    Use `Type.do_init` instead.
    #    Remember to use `Compiler.add_type` to register a type.
    #    Do NOT create instances of any `Type` by yourself, use
    #    `Compiler.types[<Type class>]` to get `Type` instance
    #  - Define at least one subclass of `AcaciaExpr`, which represents the
    #    objects of this type.
    #    Every subclasses should check whether they need to override the
    #    `export_novalue` method. Make sure to check the default definition and
    #    comments of this method below.
    #    NOTE a special case is that, `CallResult` has implemented
    #    this method for you, so it's not necessary to consider this
    #    for CallResults
    # Extra things for "storable" types to implement:
    #  - at least one (usually 1) class that is a subclass of VarValue,
    #    to represent this kind of value that is stored in Minecraft
    #    [Reason]: "variables" always hold a muttable thing. Therefore,
    #    only "storable" types can be assigned to variables.
    #  - at least one (usually 1) class that is a subclass of CallResult,
    #    to represent this kind of value when it is used as a function result
    #    The reason is same as the reason of VarValue above
    #    Remember to use `Compiler.add_call_result` to register CallResults
    #  - `export` method, for assigning the value to another VarValue
    #    (of the same type)
    #  - the class that defines this type (subclass of Type) should have
    #    a `new` method, to allow creating a new VarValue (of the same type)
    # Take builtin `int` as an example:
    #  `IntVar`, which holds a Minecraft score, is implemented (1st rule)
    #  `IntCallResult`, which holds an int function result, is implemented
    #  (2nd rule)
    #  All the AcaciaExprs of `int` type implements `export` (3rd rule)
    #  `BuiltinIntType` does have a `new` method, which create new `IntVar`s
    #  (4th rule)
    # --- CONTRIBUTOR GUIDE END ---
    # Here are the methods that have special meanings:
    #  - `call`: When calling an AcaciaExpr, this method is called
    #  - `_init_class`: Used to add attributes/methods about operators,
    #    (before the decorator works) (See `_AcaciaExprMeta`)
    def __init__(self, type, compiler):
        # compiler:Compiler master
        # type:Type type of expression
        self.compiler = compiler
        self.type = type
        self.attribute_table = AttributeTable()
    
    @classmethod
    def _init_class(cls):
        # See metaclass _AcaciaExprMeta
        pass
    
    def call(self, args, keywords):
        # call this expression
        # not implemented -> uncallable
        self.compiler.error(ErrorType.UNCALLABLE, expr_type = self.type.name)
    
    def export(self, var):
        # var:VarValue
        # return a list of str, which are commands that assigns
        # value of self to that var
        # Since we need a VarValue here, only "storable" types need
        # to implement this
        raise NotImplementedError
    
    def export_novalue(self):
        # NOTE this must be implemented by subclasses
        # this method should return a list of str, which are commands that
        # is exported when self is used as an ExprStatement (just an
        # expression)
        # e.g.:
        #  a = 1
        #  a + 1
        # Here `a + 1` is an ExprStatement, and `IntOpGroup.export_novalue`
        # is called so that compiler knows what commands to generate for this
        # line.
        # Default: Generates no command for this `ExprStatement`
        return []

class ArgumentHandler:
    # a tool to match the arguments against the given definition
    # this class also creates a VarValue for every args
    # (when calling function, arguments are passed using these vars)
    # used by AcaciaFunction
    def __init__(self, args, arg_types, arg_defaults, compiler):
        # args, arg_types, arg_defaults: same as these in ast.FunctionDef
        # these arguments decide the pattern of this callable
        self.args = args
        self.arg_types = arg_types
        self.arg_defaults = arg_defaults
        self.ARG_LEN = len(self.args)
        self.compiler = compiler

        # create a VarValue for every args according to their types
        # and store them as dict at self.arg_vars
        # meanwhile, check whether arg types are supported
        self.arg_vars = {} # str<arg name>:VarValue<place to store the arg>
        for arg in self.args:
            type_ = self.arg_types[arg]
            try:
                self.arg_vars[arg] = type_.new_var()
            except NotImplementedError:
                # type.new_var() is not implemented
                self.compiler.error(
                    ErrorType.UNSUPPORTED_ARG_TYPE,
                    arg = arg, arg_type = type_.name
                )
    
    def match(self, args: list, keywords: dict) -> dict:
        # match the definition with these given args
        # args:iterable[AcaciaExpr] Positioned args
        # keywords:dict{str<arg>:AcaciaExpr} Keyword args
        # return a dict, keys are argument names,
        # values are AcaciaExpr, meaning the value of these args
        if len(args) > self.ARG_LEN:
            self.compiler.error(ErrorType.TOO_MANY_ARGS)
        res = dict.fromkeys(self.args)
        # util
        def _check_arg_type(arg: str, value: AcaciaExpr):
            # check if `arg` got the correct type of `value`
            if value.type is not self.arg_types[arg]:
                self.compiler.error(
                    ErrorType.WRONG_ARG_TYPE,
                    arg = arg,
                    expect = self.arg_types[arg].name,
                    got = value.type.name
                )
        # positioned
        for i, value in enumerate(args):
            arg = self.args[i]
            _check_arg_type(arg, value)
            res[arg] = value
        # keyword
        for arg, value in keywords.items():
            # check multiple values of the same var
            if arg not in self.args:
                self.compiler.error(
                    ErrorType.UNEXPECTED_KEYWORD_ARG, arg = arg
                )
            if res[arg] is not None:
                self.compiler.error(ErrorType.ARG_MULTIPLE_VALUES, arg = arg)
            _check_arg_type(arg, value)
            res[arg] = value
        # if any args are missing use default if exists, else error
        for arg, value in res.copy().items():
            if value is None:
                if arg in self.arg_defaults:
                    res[arg] = self.arg_defaults[arg]
                else:
                    self.compiler.error(ErrorType.MISSING_ARG, arg = arg)
        return res
    
    def match_and_assign(self, args, keywords) -> list:
        # match the given args
        # and return a list of commands that assigns args to self.arg_vars
        args = self.match(args, keywords)
        # Assign arguments
        res = []
        for arg, value in args.items():
            res.extend(value.export(self.arg_vars[arg]))
        return res
    
    def register_args_to_scope(self, scope):
        # register arguments to the given scope
        # scope:ScopedSymbolTable
        for arg in self.args:
            scope.create(arg, self.arg_vars[arg])

class VarValue(AcaciaExpr):
    # VarValues are special AcaciaExprs that can be assigned
    # So far, only 3 types have their VarValue: int, bool and nonetype,
    # meaning users can create new variables of int or bool type
    # VarValues are also used to hold temporary variables
    # e.g. 1 + 2 -> IntLiteral(3) -> Unassignable
    # e.g. a -> IntVar("acacia", "acacia3") -> Assignable
    # e.g. |"x": "y"| -> IntVar("y", "x") -> Assignable
    # e.g. bool -> Type -> Unassignable
    pass

class CallResult(AcaciaExpr):
    # call result of an AcaciaFunction
    # This is like a VarValue with dependencies
    # "storable" types must implement a subclass of this
    # These classes are automatically called by ./callable.py,
    # so they should always receive these args:
    #  `dependencies`, `result_var`, `compiler`
    def __init__(
        self, dependencies: list, result_var: VarValue, type, compiler
    ):
        super().__init__(type, compiler)
        self.dependencies = dependencies
        self.result_var = result_var
    
    def export(self, var: VarValue):
        return self.dependencies + self.result_var.export(var)
    
    def export_novalue(self):
        return self.dependencies + self.result_var.export_novalue()
    
    def __str__(self):
        return str(self.result_var)
