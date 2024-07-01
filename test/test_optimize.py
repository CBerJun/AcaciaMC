# Add `acaciamc` directory to path
import os
import sys

sys.path.append(os.path.realpath(
    os.path.join(__file__, os.pardir, os.pardir)
))

from acaciamc.mccmdgen import optimizer, cmds


class MyOpt(optimizer.Optimizer):
    def entry_files(self):
        return [f1]

    max_inline_file_size = 30

    def dump(self):
        return ('\n\n'.join(
            str(file) + '\n' + file.to_str(debugging=True)
            for file in self.files
        ))


project = MyOpt("scb")
f1 = cmds.MCFunctionFile("test/path1")
f2 = cmds.MCFunctionFile("test/path2")
f3 = cmds.MCFunctionFile("test/path3")
f4 = cmds.MCFunctionFile("test/path4")
f5 = cmds.MCFunctionFile("test/path5")
project.add_file(f1)
project.add_file(f2)
project.add_file(f3)
project.add_file(f4)
project.add_file(f5)
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
f1.write(cmds.Execute(
    [cmds.ExecuteEnv("as", "@p")],
    # [cmds.ExecuteCond("entity", "@p")],
    cmds.InvokeFunction(f4)
))
f1.write(cmds.RawtextOutput(
    "tellraw @a", cmds.Rawtext([cmds.RawtextScore(v2)])
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

f4.write(cmds.Execute(
    [cmds.ExecuteCond("block", "~~~ air")],
    cmds.InvokeFunction(f5)
))

f5.write(cmds.Cmd("say cmd5: 1"))
f5.write(cmds.Cmd("say cmd5: 2"))

print(project.dump())
project.optimize()
print("\n==========================\n")
print(project.dump())
