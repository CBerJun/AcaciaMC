# Acacia
[English](README.md) | 中文

## 简介
**Acacia 是一门运行在 Minecraft 基岩版的编程语言。**
Minecraft 的命令较为复杂、很长、且难以维护。
Acacia 是命令的替代，它也是用来操控 Minecraft 的，*但是*它的语法相对命令清晰很多、且便于维护，能提升开发效率。
**想象一下: 仅用写不到14KB代码就能编写一个在 Minecraft 里运行的俄罗斯方块小游戏** (见[下文](#acacia-能干什么))!

Acacia 代码最终会被编译为多个 `.mcfunction` 文件，也就是说 Acacia 其实仍会被程序转换为命令，再通过行为包被加载进一个世界来执行。

还是很疑惑吗? 举个例子吧，这段 Acacia 代码可以在 Minecraft 中计算等差数列和:
```python
import print
def arithmetic(start: int, to: int, delta=1) -> int:
    #* 返回以`start`为首项，`to`为末项，`delta`为公差的等差数列的和 *#
    result := (start + to) * ((to - start) / delta + 1) / 2
res := arithmetic(-30, 14, delta=2)
print.tell(print.format("从-30到14，公差为2的等差数列和为%0", res))
```
Acacia 可以把上面这段代码转换为命令:
```mcfunction
# 这些是自动生成的! 很酷吧?
scoreboard players set acacia1 acacia -30
scoreboard players set acacia2 acacia 14
scoreboard players set acacia3 acacia 2
scoreboard players operation acacia8 acacia = acacia2 acacia
scoreboard players operation acacia8 acacia -= acacia1 acacia
scoreboard players operation acacia8 acacia /= acacia3 acacia
scoreboard players add acacia8 acacia 1
scoreboard players operation acacia7 acacia = acacia8 acacia
scoreboard players operation acacia6 acacia = acacia1 acacia
scoreboard players operation acacia6 acacia += acacia2 acacia
scoreboard players operation acacia6 acacia *= acacia7 acacia
scoreboard players operation acacia6 acacia /= acacia5 acacia
scoreboard players operation acacia4 acacia = acacia6 acacia
scoreboard players operation acacia9 acacia = acacia4 acacia
tellraw @a {"rawtext": [{"text": "从-30到14，公差为2的等差数列和为"}, {"score": {"objective": "acacia", "name": "acacia9"}}]}
```
```mcfunction
# 初始化: 创建计分板并建立常量
scoreboard objectives add acacia dummy
scoreboard players set acacia5 acacia 2
```
运行这些生成的命令，就会在 Minecraft 聊天栏输出:
> 从-30到14，公差为2的等差数列和为-184

**总结一下，使用 Acacia 可以制作 Minecraft 的项目——但不是利用命令，而是利用 Acacia 代码，它阅读和维护起来都更加简单。**

Acacia 是使用 Python 编写的，所以编译器 (就是把代码转换为命令的程序) 需要 Python（需要 3.6 或以上版本）来运行。

## Acacia 能干什么?
一些实例:
- **一条命令都不用写**，就可以做一个在 Minecraft 中运行的俄罗斯方块!
  在[这里](test/demo/tetris.aca)查看它的源码。
  源码只有14KB! 而生成出来的命令却多达约280KB，约50个文件。
- 仍旧是一条命令都不用写，就可以制作一个 Minecraft 迷宫随机生成器，源码仅3.5KB
  (不算解释算法用的注释)。查看[源码](test/demo/maze.aca)。
- 通过内置模块 `music` 可以从乐谱自动生成红石音乐。

具体功能:
- 不用管理一堆函数文件、看冗长的命令了; Acacia 代码十分简洁。
- 不用再担心 `/execute` 运行环境了。
- 不用捣鼓实体标签了; Acacia 有非常独特的实体系统!
- 不用捣鼓计分板了; 取而代之的是编程中常见的变量系统。
- 不用穷举一堆重复命令了; Acacia 很擅长生成重复命令。
- 可以定义分支、循环结构。
- 编译时常量内容丰富，包括数字、字符串、数组、映射表、甚至坐标等，使作品更加灵活。

查看[这个文件](test/brief.aca)来了解更多关于 Acacia 语法的信息。

## 语法概览
这是在 Acacia 中定义变量的方法: `a := 1`。
就这么简单捏，无需研究计分板系统了。

一行代码计算复杂的表达式:
```python
a := 10
b := (10 + a) * a - 5
```

定义函数:
```python
def foo(x: int, y = True) -> int:
    # 这里是函数体代码
    result := x
    if y:
        result += 10
z: int
# 下面这些都是合法的调用:
foo(1)
z = foo(2, False)
z = foo(x=3)
```

控制语句 (分支、循环):
```python
def is_prime(x: int) -> bool:
    #* 检测`x`是不是质数 *#
    result: bool = True
    mod: int = 2
    result = True
    while mod <= x / 2:
        if x % mod == 0:
            result = False
        mod += 1
```

丰富的内置模块:
```python
import print
money := 10
# 在聊天栏向所有人输出"Hello, world!"
print.tell("Hello world!")
# 在所有玩家的快捷栏上方显示"Money: (money变量的数值)"
print.title(print.format("Money: %0", money), mode=print.ACTIONBAR)
```
```python
import music
# 自动生成红石音乐，并采用1.2倍速。
m -> music.Music("music_score.mid", speed=1.2)
m.play()
```

利用常量和`for`来避免重复性代码:
```python
import world

# 根据变量的值放置不同颜色的混凝土方块
COLORS -> {
    0: "cyan", 1: "orange", 2: "yellow",
    3: "purple", 4: "lime", 5: "red", 6: "blue"
}
i := 0  # 计算`i`...
for c in COLORS:
    if c == i:
        world.setblock(
            Pos(0, -50, 0),
            world.Block("concrete", {"color": COLORS[c]})
        )
```

实体、坐标系统:
```python
import world

ORIGIN -> AbsPos(0, -50, 0)
world.fill(ORIGIN, Offset().offset(x=5, z=5),
           world.Block("concrete", {"color": "red"}))

entity Test:
    @type: "armor_stand"
    @position: ORIGIN

    def __init__():
        world.setblock(Pos(self), "diamond_block")
        world.effect_give(self, "invisibility", duration=1000)

    def foo():
        world.tp(self, ORIGIN)

test_group: Engroup[Test]
test_group.select(Enfilter().distance_from(ORIGIN, max=5))
for test in test_group:
    test.foo()
```

## 了解更多
- [一个中文的介绍视频](https://www.bilibili.com/video/BV1uR4y167w9)
- [用 Acacia 生成红石音乐](https://www.bilibili.com/video/BV1f24y1L7DB)
- 查看[这个测试文件](test/brief.aca)来详细了解 Acacia 语法!
- 在[这里](test/demo/numguess.aca)可以找到一个简单的猜数字demo!
