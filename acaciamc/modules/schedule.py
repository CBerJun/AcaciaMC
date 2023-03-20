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
from acaciamc.ast import Operator

class TaskType(Type):
    """Task(target: function): A task manager"""
    name = "Task"

    def do_init(self):
        def _new(func: BinaryFunction):
            target = func.arg_require("target", BuiltinFunctionType)
            other_arg, other_kw = func.arg_raw()
            return Task(target, other_arg, other_kw, self.compiler)
        self.attribute_table.set(
            "__new__", BinaryFunction(_new, self.compiler)
        )

class Task(AcaciaExpr):
    def __init__(self, target: AcaciaExpr, other_arg, other_kw, compiler):
        """
        target: The function to call
        other_arg & other_kw: Arguments to pass to `target`
        """
        super().__init__(compiler.types[TaskType], compiler)
        # Define an `int` which show how many ticks left before the function
        # runs; it is -1 when no request exists.
        self.timer = compiler.types[BuiltinIntType].new_var()
        # self._target_args, self._target_keywords: args to pass to `target`
        self._target_args, self._target_keywords = [], {}
        def _timer_reset(func: BinaryFunction):
            cmds = IntLiteral(-1, compiler).export(self.timer)
            return result_none(cmds, compiler)
        def _after(func: BinaryFunction):
            """.after(delay: int): Run the target after `delay`"""
            delay = func.arg_require("delay", BuiltinIntType)
            func.assert_no_arg()
            cmds = delay.export(self.timer)
            return result_none(cmds, compiler)
        def _cancel(func: BinaryFunction):
            """.cancel(): Cancel the schedule"""
            func.assert_no_arg()
            return _timer_reset(func)
        def _has_schedule(func: BinaryFunction):
            """.has_schedule() -> bool: Get whether a schedule exists"""
            # Just return whether timer >= 0
            func.assert_no_arg()
            return BoolCompare(
                self.timer, Operator.greater_equal, IntLiteral(0, compiler),
                compiler
            )
        self.attribute_table.set(
            "__init__", BinaryFunction(_timer_reset, compiler)
        )
        self.attribute_table.set("_timer", self.timer)
        self.attribute_table.set("after", BinaryFunction(_after, compiler))
        self.attribute_table.set(
            "cancel", BinaryFunction(_cancel, compiler)
        )
        self.attribute_table.set(
            "has_schedule", BinaryFunction(_has_schedule, compiler)
        )
        # Write tick.mcfunction
        self.compiler.file_tick.write_debug("# schedule.Task")
        result = target.call(other_arg, other_kw)
        cmds = result.export_novalue()
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

def _register_loop(func: BinaryFunction):
    """
    schedule.register_loop(
        target: function, interval: int = 1, *args, **kwargs
    )
    Call a function repeatly every `interval` ticks with `args` and `kwargs`.
    """
    # Parse args
    target = func.arg_require("target", BuiltinFunctionType)
    arg_interval = func.arg_optional(
        "interval", IntLiteral(1, func.compiler), BuiltinIntType
    )
    if not isinstance(arg_interval, IntLiteral):
        func.arg_error("interval", "must be a constant")
    if arg_interval.value <= 0:
        func.arg_error("interval", "must be positive")
    other_arg, other_kw = func.arg_raw()
    # Allocate an int for timer
    timer = func.compiler.types[BuiltinIntType].new_var()
    # Initialize
    init_cmds = IntLiteral(0, func.compiler).export(timer)
    # Tick loop
    func.compiler.file_tick.write_debug("# schedule.register_loop")
    ## Call on times up AND reset timer
    result = target.call(other_arg, other_kw)
    cmds = result.export_novalue()
    cmds.extend(arg_interval.export(timer))
    func.compiler.file_tick.extend(
        export_execute_subcommands(
            ["if score %s matches 0" % timer], main=cmd
        )
        for cmd in cmds
    )
    ## Let the timer -1
    func.compiler.file_tick.extend(timer.isub(IntLiteral(1, func.compiler)))
    # Result
    return result_none(init_cmds, func.compiler)

def acacia_build(compiler):
    compiler.add_type(TaskType)
    return {
        "Task": compiler.types[TaskType],
        "register_loop": BinaryFunction(_register_loop, compiler)
    }
