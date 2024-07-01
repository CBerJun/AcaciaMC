"""
schedule - Working through game ticks

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
    Foo called with arg 10
Note that, when 1 request is already sent using `after` and the function
is not called yet (within 20 ticks in this example), and another `after`
request is sent, the first one is overrided.
`task.has_schedule` returns whether a request already exists.
`task._timer` (int) shows how many ticks left before the target called
and is -1 when no request exists.

`Task`s can be registered to be called when a certain area of world is
loaded (`task.on_area_loaded`, `task.on_circle_loaded`,
`task.on_tickingarea`). Note these schedules cannot be canceled and
are not tracked by `task.has_schedule`.

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

from typing import TYPE_CHECKING

import acaciamc.mccmdgen.cmds as cmds
from acaciamc.ast import Operator
from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.objects import *
from acaciamc.tools import axe, resultlib, method_of

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler


class TaskDataType(DefaultDataType):
    name = "Task"


ctdt_task = CTDataType("Task")


class TaskType(Type):
    """
    Task(target: function, *args, **kwds)
    A task manager that calls the given function after a period of time.
    The `args` and `kwds` are passed to the function.
    """

    def do_init(self):
        @method_of(self, "__new__")
        @axe.chop
        @axe.arg("target", axe.Callable())
        @axe.star_arg("args", axe.AnyValue())
        @axe.kwds("kwds", axe.AnyValue())
        def _new(compiler, target, args, kwds):
            res = Task(target, args, kwds, compiler)
            return res, res.timer_reset()

    def datatype_hook(self):
        return TaskDataType()

    def cdatatype_hook(self):
        return ctdt_task


class Task(ConstExprCombined):
    cdata_type = ctdt_task

    def __init__(self, target: AcaciaCallable, other_arg, other_kw,
                 compiler: "Compiler"):
        """
        target: The function to call
        other_arg & other_kw: Arguments to pass to `target`
        """
        super().__init__(TaskDataType())
        # Define an `int` which show how many ticks left before the function
        # runs; it is -1 when no request exists.
        self.timer = IntVar.new(compiler)
        # Allocate a file to call the given function
        self.target_file = cmds.MCFunctionFile()
        compiler.add_file(self.target_file)
        _res, call_cmds = target.call_withframe(
            other_arg, other_kw, compiler, location="<schedule.Task>"
        )
        self.target_file.extend(call_cmds)

        @method_of(self, "after")
        @axe.chop
        @axe.arg("delay", IntDataType)
        def _after(compiler, delay: AcaciaExpr):
            """.after(delay: int): Run the target after `delay`"""
            commands = delay.export(self.timer, compiler)
            return resultlib.commands(commands)

        @method_of(self, "cancel")
        @axe.chop
        def _cancel(compiler):
            """.cancel(): Cancel the schedule created by `after`."""
            return resultlib.commands(self.timer_reset())

        @method_of(self, "has_schedule")
        @axe.chop
        def _has_schedule(compiler):
            """
            .has_schedule() -> bool
            Whether a schedule created by `after` is in progress.
            """
            # Just return whether timer >= 0
            return self.timer.compare(
                Operator.greater_equal, IntLiteral(0), compiler
            )

        @method_of(self, "on_area_loaded")
        @axe.chop
        @axe.arg("origin", PosDataType)
        @axe.arg("offset", PosOffsetDataType)
        def _on_area_loaded(compiler, origin: Position, offset: PosOffset):
            """
            .on_area_loaded(origin: Pos, offset: Offset)
            Run function when the given area is loaded.
            """
            return resultlib.commands([cmds.Execute(
                origin.context,
                runs=cmds.ScheduleFunction(
                    self.target_file, "on_area_loaded add ~ ~ ~ %s" % offset
                ),
            )])

        @method_of(self, "on_circle_loaded")
        @axe.chop
        @axe.arg("origin", PosDataType)
        @axe.arg("radius", axe.RangedLiteralInt(0, None))
        def _on_circle_loaded(compiler, origin: Position, radius: int):
            """
            .on_circle_loaded(origin: Pos, radius: int-literal)
            Run function when the given circle with `origin` as origin
            and `radius` as radius (chunks) is loaded.
            """
            return resultlib.commands([cmds.Execute(
                origin.context,
                runs=cmds.ScheduleFunction(
                    self.target_file,
                    "on_area_loaded add circle ~ ~ ~ %d" % radius
                )
            )])

        @method_of(self, "on_tickingarea")
        @axe.chop
        @axe.arg("name", axe.LiteralString())
        def _on_tickingarea(compiler, name: str):
            """
            .on_tickingarea(name: str)
            Run function when the given ticking area is added.
            """
            return resultlib.commands([
                cmds.ScheduleFunction(
                    self.target_file,
                    "on_area_loaded add tickingarea %s" % name
                ),
            ])

        self.attribute_table.set("_timer", self.timer)
        # Write tick.mcfunction
        compiler.file_tick.write_debug("# schedule.Task")
        compiler.file_tick.write(
            cmds.Execute(
                [cmds.ExecuteScoreMatch(self.timer.slot, "0")],
                runs=cmds.InvokeFunction(self.target_file)
            ),
            # Decrease the timer by 1
            cmds.Execute(
                [cmds.ExecuteScoreMatch(self.timer.slot, "0..")],
                runs=cmds.ScbRemoveConst(self.timer.slot, 1)
            )
        )

    def timer_reset(self) -> CMDLIST_T:
        return [cmds.ScbSetConst(self.timer.slot, -1)]


@axe.chop
@axe.arg("target", axe.Callable())
@axe.arg("interval", IntDataType, default=IntLiteral(1))
@axe.star_arg("args", axe.AnyValue())
@axe.kwds("kwds", axe.AnyValue())
def register_loop(compiler: "Compiler", target: AcaciaCallable,
                  interval: AcaciaExpr, args, kwds):
    """
    schedule.register_loop(
        target: function, interval: int-literal = 1, *args, **kwds
    )
    Call a function repeatly every `interval` ticks with `args` and `kwds`.
    """
    _res, tick_commands = target.call_withframe(
        args, kwds, compiler, location="<schedule.register_loop>"
    )
    compiler.file_tick.write_debug("# schedule.register_loop")
    # Optimization: if the interval is 1, no need for timer
    if isinstance(interval, IntLiteral) and interval.value == 1:
        compiler.file_tick.extend(tick_commands)
        return None
    # Allocate an int for timer
    timer = IntVar.new(compiler)
    # Initialize
    init_cmds = [cmds.ScbSetConst(timer.slot, 0)]
    # Tick loop
    ## Call on times up AND reset timer
    tick_commands.extend(interval.export(timer, compiler))
    compiler.file_tick.extend(
        cmds.execute(
            [cmds.ExecuteScoreMatch(timer.slot, "..0")], runs=cmd
        )
        for cmd in tick_commands
    )
    ## Decrease the timer by 1
    compiler.file_tick.write(cmds.ScbRemoveConst(timer.slot, 1))
    # Result
    return resultlib.commands(init_cmds)


def acacia_build(compiler):
    return {
        "Task": TaskType(),
        "register_loop": BinaryFunction(register_loop)
    }
