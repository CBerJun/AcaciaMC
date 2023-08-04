"""
`schedule` is an Acacia module for running something after a period of time.

The `Task` object stands for a task manager.
e.g.
    import schedule
    import print
    def foo(arg: int):
        print.tell(print.format("Foo called with arg %0", arg))
    print.tell("Start")
    task -> schedule.Task(foo, arg=10)
    task.after(20)
result:
    Start
    [1 second (20 ticks) later]
    Foo called 10
Note that, when 1 request is already sent using `after` and the function
is not called yet (within 20 ticks in this example), and another `after`
request is sent, the first one is overrided.
`task.has_schedule` returns whether a request already exists.
`task.timer` (int) shows how many ticks left before the target called and
is -1 when no request exists.

`register_loop` register a function to be called repeatedly.
e.g.
    import schedule
    import print
    def foo():
        print.tell("Foo Called")
    schedule.register_loop(foo, interval=2)
result:
    Foo Called
    [2 ticks later]
    Foo Called
    [2 ticks later]
    Foo Called
    ...
"""

from acaciamc.mccmdgen.expression import *
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.ast import Operator
from acaciamc.tools import axe, resultlib, method_of

class TaskDataType(DefaultDataType):
    name = "Task"

class TaskType(Type):
    """
    Task(target: function, *args, **kwds)
    A task manager that calls the given function after a period of time.
    The `args` and `kwds` are passed to the function.
    """
    def do_init(self):
        @method_of(self, "__new__")
        @axe.chop
        @axe.arg("target", FunctionDataType)
        @axe.star_arg("args", axe.AnyValue())
        @axe.kwds("kwds", axe.AnyValue())
        def _new(compiler, target, args, kwds):
            return Task(target, args, kwds, compiler)

    def datatype_hook(self):
        return TaskDataType()

class Task(AcaciaExpr):
    def __init__(self, target: AcaciaExpr, other_arg, other_kw, compiler):
        """
        target: The function to call
        other_arg & other_kw: Arguments to pass to `target`
        """
        super().__init__(TaskDataType(), compiler)
        # Define an `int` which show how many ticks left before the function
        # runs; it is -1 when no request exists.
        self.timer = IntDataType(compiler).new_var()
        self._target_args, self._target_keywords = [], {}
        def _timer_reset():
            cmds = IntLiteral(-1, compiler).export(self.timer)
            return resultlib.commands(cmds, compiler)
        @method_of(self, "after")
        @axe.chop
        @axe.arg("delay", IntDataType)
        def _after(compiler, delay: AcaciaExpr):
            """.after(delay: int): Run the target after `delay`"""
            cmds = delay.export(self.timer)
            return resultlib.commands(cmds, compiler)
        @method_of(self, "cancel")
        @axe.chop
        def _cancel(compiler):
            """.cancel(): Cancel the schedule"""
            return _timer_reset()
        @method_of(self, "__init__")
        def _init(compiler, args, keywords):
            return _timer_reset()
        @method_of(self, "has_schedule")
        @axe.chop
        def _has_schedule(compiler):
            """.has_schedule() -> bool: Get whether a schedule exists"""
            # Just return whether timer >= 0
            return BoolCompare(
                self.timer, Operator.greater_equal, IntLiteral(0, compiler),
                compiler
            )
        self.attribute_table.set("_timer", self.timer)
        # Write tick.mcfunction
        self.compiler.file_tick.write_debug("# schedule.Task")
        _res, cmds = target.call(other_arg, other_kw)
        self.compiler.file_tick.extend(
            export_execute_subcommands(
                ["if score %s matches 0" % self.timer], main=cmd
            )
            for cmd in cmds
        )
        # Let the timer -1
        self.compiler.file_tick.extend(
            export_execute_subcommands(
                ["if score %s matches 0.." % self.timer], main=cmd
            )
            for cmd in self.timer.isub(IntLiteral(1, self.compiler))
        )

def _create_register_loop(compiler):
    @axe.chop
    @axe.arg("target", FunctionDataType)
    @axe.arg("interval", IntDataType, default=IntLiteral(1, compiler))
    @axe.star_arg("args", axe.AnyValue())
    @axe.kwds("kwds", axe.AnyValue())
    def _register_loop(compiler, target: AcaciaExpr,
                    interval: AcaciaExpr, args, kwds):
        """
        schedule.register_loop(
            target: function, interval: int-literal = 1, *args, **kwds
        )
        Call a function repeatly every `interval` ticks with `args` and `kwds`.
        """
        # Allocate an int for timer
        timer = IntDataType(compiler).new_var()
        # Initialize
        init_cmds = IntLiteral(0, compiler).export(timer)
        # Tick loop
        compiler.file_tick.write_debug("# schedule.register_loop")
        ## Call on times up AND reset timer
        _res, cmds = target.call(args, kwds)
        cmds.extend(interval.export(timer))
        compiler.file_tick.extend(
            export_execute_subcommands(
                ["if score %s matches ..0" % timer], main=cmd
            )
            for cmd in cmds
        )
        ## Let the timer -1
        compiler.file_tick.extend(timer.isub(IntLiteral(1, compiler)))
        # Result
        return resultlib.commands(init_cmds, compiler)
    return _register_loop

def acacia_build(compiler):
    register_loop = _create_register_loop(compiler)
    return {
        "Task": TaskType(compiler),
        "register_loop": BinaryFunction(register_loop, compiler)
    }
