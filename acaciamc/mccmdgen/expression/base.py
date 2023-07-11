"""Base stuffs for generating codes of Acacia expressions."""

__all__ = [
    # Utils
    'export_execute_subcommands', 'ArgumentHandler',
    'export_need_tmp',
    # Base class
    'AcaciaExpr', 'VarValue',
    # Type checking
    'ARGS_T', 'KEYWORDS_T', 'CALLRET_T'
]

from typing import List, TYPE_CHECKING, Union, Callable, Dict, Tuple

from acaciamc.mccmdgen.symbol import AttributeTable
from acaciamc.error import *

if TYPE_CHECKING:
    from .types import DataType
    from acaciamc.compiler import Compiler

### --- UTILS --- ###

def export_execute_subcommands(subcmds: List[str], main: str) -> str:
    """Convert a list of /execute subcommands into a command.
    e.g. cmds = ['if xxx', 'as xxx'], main = 'say ...'
         returns: 'execute if xxx as xxx run say ...'
    """
    if main.strip().startswith("#"):
        # A comment
        return main
    if not subcmds:
        # optimization: if no subcommand given
        return main
    return " ".join(("execute", *subcmds, "run", main))

def export_need_tmp(func):
    """Decorator for `AcaciaExpr.export`.
    Usually when we do `A.export(B)`, the value of `A` is dumped to
    `B` directly without a temporary value.
    This decorator add a temporary value `T`, first `A.export(T)`,
    then `T.export(B)`.
    This is to prevent changing the value of `B` too early.
    WITHOUT a temporary value, take `a = 1 + a` as an example,
    we let `a` = 1 first, and then plus `a` itself to it, which is 1
    now, so whatever `a` is before assigning, it becomes 2 now.
    """
    def _decorated(self, var: VarValue):
        assert isinstance(self, AcaciaExpr)
        temp = self.data_type.new_var(tmp=True)
        cmds = []
        cmds.extend(func(self, temp))
        cmds.extend(temp.export(var))
        return cmds
    return _decorated

### --- END UTILS --- ###

ARGS_T = List["AcaciaExpr"]  # Positional arguments
KEYWORDS_T = Dict[str, "AcaciaExpr"]  # Keyword arguments
CALLRET_T = Tuple["AcaciaExpr", List[str]]  # Result

class AcaciaExpr:
    """Base class for EVERYTHING that represents an Acacia expression.
    NOTE Contributer Guide:
    There are 2 types of Acacia data types:
    - The "storable" types. These types of expressions are stored in
      Minecraft, and their values can be changed when running the code
      (since it is stored in MC).
      e.g. int, bool
    - The "unstorable" types. These types of expression cannot be stored
      in Minecraft, and is only tracked by the compiler. Therefore,
      their values can't be changed.
      e.g. str, module, function
    To define a new type, you need to:
     - Define a subclass of `Type` that represents this type.
       The `name` (str) attribute must be given which is the name of
       type user sees.
       Please notice not to use `Type.__init__` for initializations!
       Use `Type.do_init` instead.
       Remember to use `Compiler.add_type` to register a type.
       Do NOT create instances of any `Type` by yourself, use
       `Compiler.types[<Type class>]` to get `Type` instance.
     - Define at least one subclass of `AcaciaExpr`, which represents
       the objects of this type.
       `call` is a special method that would be called when this
       expression is called in Acacia.
       `cmdstr` is a special method that returns the string
       representation of this expression used in raw command
       substitution.
    Extra things for "storable" types to implement:
     - at least one (usually 1) class that is a subclass of `VarValue`,
       to represent this kind of value that is stored in Minecraft.
     - `export` method, called when user assigns the value of this
       expression to a `VarValue` of same type.
     - the class that defines this type (subclass of `Type`) should have
       a `new_var` method, to allow creating a new `VarValue` of this
       type.
    Take builtin "int" as an example:
     - `IntVar`, which holds a Minecraft score, is implemented.
     - All the AcaciaExprs of `int` type implements `export`.
     - `IntType` does have a `new_var` method, which creates a new
     `IntVar`.

    To implement operator for your type, here are some methods:
     - __add__, __sub__, __mul__, __floordiv__, __mod__: represents
       binary +, -, *, /, %, respectively. See also __radd__,
       __rsub__, etc.
     - __pos__, __neg__, not_: represents unary +, - and "not",
       respectively.
     - iadd, isub, imul, idiv, imod: represents +=, -=, *=, /=, %=
       respectively.
    When you are not satisfied with input operand type, please raise
    `TypeError`, EXCEPT for binary operators (return `NotImplemented`
    instead).
    """
    def __init__(self, type_: "DataType", compiler: "Compiler"):
        self.compiler = compiler
        self.data_type = type_
        self.attribute_table = AttributeTable()

    def call(self, args: ARGS_T, keywords: KEYWORDS_T) -> CALLRET_T:
        """Call this expression.
        Return value:
         1st element: Result of this call
         2nd element: Commands to run
        If this is not implemented, then the object is uncallable.
        """
        raise Error(ErrorType.UNCALLABLE, expr_type=str(self.data_type))

    def export(self, var: "VarValue") -> List[str]:
        """Return the commands that assigns value of `self` to `var`.
        Since we need a `VarValue` here, only "storable" types need
        to implement this.
        The method can be decorated with `export_need_tmp`.
        """
        raise NotImplementedError

    def cmdstr(self) -> str:
        """Return a string representation of this expression, used in
        raw commands. If not implemented, then the object can not be
        formatted in a command.
        """
        raise NotImplementedError

class ArgumentHandler:
    """A tool to match function arguments against a given definition."""
    def __init__(self, args: List[str], arg_types: Dict[str, "DataType"],
                 arg_defaults: Dict[str, Union[AcaciaExpr, None]]):
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

    def match(self, args: ARGS_T,
              keywords: KEYWORDS_T) -> Dict[str, AcaciaExpr]:
        """Match the expected pattern with given call arguments.
        Return a `dict` mapping names to argument value.
        """
        if len(args) > self.ARG_LEN:
            raise Error(ErrorType.TOO_MANY_ARGS)
        res = dict.fromkeys(self.args)
        # util
        def _check_arg_type(arg: str, value: AcaciaExpr):
            # check if `arg` got the correct type of `value`
            t = self.arg_types[arg]
            if (t is not None) and (not t.matches(value.data_type)):
                raise Error(
                    ErrorType.WRONG_ARG_TYPE, arg=arg,
                    expect=str(t), got=str(value.data_type)
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
                raise Error(ErrorType.UNEXPECTED_KEYWORD_ARG, arg=arg)
            if res[arg] is not None:
                raise Error(ErrorType.ARG_MULTIPLE_VALUES, arg=arg)
            _check_arg_type(arg, value)
            res[arg] = value
        # if any args are missing use default if exists, else error
        for arg, value in res.copy().items():
            if value is None:
                if arg in self.arg_defaults:
                    res[arg] = self.arg_defaults[arg]
                else:
                    raise Error(ErrorType.MISSING_ARG, arg=arg)
        return res

class VarValue(AcaciaExpr):
    """`VarValue`s are special `AcaciaExpr`s that can be assigned to.
    Examples are builtin int, bool and nonetype.
    Users can create new variables of these types.
    `VarValue`s are also used to hold temporary variables.
    e.g. 1 + 2 -> IntLiteral(3) -> Unassignable
    e.g. a -> IntVar("acacia", "acacia3") -> Assignable
    e.g. |"x": "y"| -> IntVar("y", "x") -> Assignable
    e.g. bool -> Type -> Unassignable
    """
    pass
