# Loop objects in Acacia
# TODO allow setting interval between loops
from .base import *
from .types import BuiltinLoopType, BuiltinBoolType
from .callable import *
from .boolean import BoolLiteral
from .none import *
from ...error import *

__all__ = ['Loop']

class Loop(AcaciaExpr):
    def __init__(self, args, arg_types, arg_defaults, compiler):
        # args & arg_types & arg_defaults:
        #   same as these in .callable.AcaciaFunction
        super().__init__(compiler.types[BuiltinLoopType], compiler)
        self.arg_handler = ArgumentHandler(
            args, arg_types, arg_defaults, self.compiler
        )
        # running_var: decide whether the loop is running
        self.running_var = self.compiler.types[BuiltinBoolType].new_var()
        # file:MCFunctionFile the target file of loop
        # when it is None, meaning empty loop;
        # it should be completed by Generator
        self.file = None

        # some attributes
        def _set_running(value: bool, func: BinaryFunction):
            func.assert_no_arg()
            # create a literal of `value` and assign it to running_var
            cmds = BoolLiteral(value, func.compiler).export(self.running_var)
            # return none with the commands generated above
            return NoneCallResult(cmds, NoneVar(func.compiler), func.compiler)
        # loop.start(...) -> 2 steps:
        # 1. pass args to vars
        # 2. self.var_running = True
        def _start(func: BinaryFunction):
            args, keywords = func.arg_raw()
            res = _set_running(True, func)
            res.dependencies.extend(
                self.arg_handler.match_and_assign(args, keywords)
            )
            return res
        self.attribute_table.create(
            'start', BinaryFunction(_start, self.compiler)
        )
        # loop.stop() -> self.var_running = False
        self.attribute_table.create(
            'stop', BinaryFunction(
                lambda f: _set_running(False, f), self.compiler
            )
        )
        # loop.is_running() -> return self.var_running == False
        def _is_running(func: BinaryFunction):
            func.assert_no_arg()
            return self.running_var
        self.attribute_table.create(
            'is_running', BinaryFunction(_is_running, self.compiler)
        )
    
    def export_tick(self) -> str:
        # export the command used in tick.mcfunction (mcfunction file
        # that is executed every ticks)
        # Every tick, if self.running_var is True, run the loop
        return export_execute_subcommands(
            subcmds = ['if score %s matches 1' % self.running_var],
            main = self.file.call()
        )
