# Add `acaciamc` directory to path
import os
import sys
sys.path.append(os.path.realpath(
    os.path.join(__file__, os.pardir, os.pardir)
))

from acaciamc.mccmdgen import optimizer, cmds
from acaciamc.constants import Config

Config.debug_comments = True

class MyOpt(optimizer.Optimizer):
    def entry_files(self):
        return [f1]

    max_inline_file_size = 30

    def dump(self):
        return ('\n'.join(
            str(file) + '\n' + file.to_str()
            for file in self.files
        ))

project = MyOpt(init_file_path="test/init")
f1 = cmds.MCFunctionFile("test/path1")
f2 = cmds.MCFunctionFile("test/path2")
f3 = cmds.MCFunctionFile("test/path3")
project.add_file(f1)
project.add_file(f2)
project.add_file(f3)
v1 = project.allocate()
v2 = project.allocate()
v3 = project.allocate()

f1.write("test command")
f1.write(cmds.ScbSetConst(v1, 10))
f1.write(cmds.ScbOperation(cmds.ScbOp.ASSIGN, v2, v1))
# c = cmds.Execute(
#     [cmds.ExecuteScoreComp(v2, v3, cmds.ScbCompareOp.GTE)],
#     cmds.InvokeFunction(f3)
# )
c = cmds.Execute(
    [cmds.ExecuteScoreMatch(v2, "114")],
    cmds.InvokeFunction(f3)
)
f1.write(c)
f1.write(cmds.RawtextOutput(
    "tellraw @a", [{"score": {"name": v2.target, "objective": v2.objective}}]
))
f1.write(cmds.ScbRandom(v2, 10, 20))

f2.write(cmds.InvokeFunction(f1))

f3.write(cmds.ScbOperation(cmds.ScbOp.ASSIGN, v1, v2))
f3.write(cmds.ScbAddConst(v2, 10))
f3.write(cmds.Execute(
    [cmds.ExecuteScoreComp(v1, v3, cmds.ScbCompareOp.GTE)],
    cmds.Cmd("test arg")
))
f3.write(cmds.ScbSetConst(v1, 20))

project.generate_init_file()
print(project.dump())
project.optimize()
print("==========================")
print(project.dump())