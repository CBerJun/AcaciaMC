# Acacia
[English](README.md) | 中文

## 简介
Acacia 是一门为 Minecraft 基岩版指令开发设计的编程语言。
Acacia 所追求的是*简单*。Minecraft 的命令较为复杂、很长、且难以维护。
Acacia 将指令简化为了类似 Python 语言的代码。
代码最终会被编译为多个 mcfunction 文件，可以通过行为包被加载进一个世界。

查看[这个文件](test/brief_intro.aca)来了解 Acacia 大概的语法。

## 简单的代码
在 Acacia 中定义变量: `a = 1`。就这么简单捏。
不需要再去搞那些计分板了。

一行代码计算复杂的表达式:
```
a = 10
# `10 + 20` 会被编译器折叠为 `30`
b = (10 + 20) * a - 5
```

定义函数:
```
def foo(x: int, y = True) -> int:
    pass # 这里写函数体代码
```

内置的模块:
```
import print
money = 10
# 在聊天栏向所有人输出"Hello, world!"
print.tell("Hello world!")
# 在所有玩家的快捷栏上方显示"Money: (money变量的数值)"
print.title(print.format("Money: %0", money), mode=print.ACTIONBAR)
```

## 与命令的兼容
Acacia 支持在代码中嵌入命令:
```
a = 1
/tp @p 11 45 14
/*
    tellraw @a {
    ...
    }
*/ # 多行命令!
```

它甚至能够帮你简化命令:
```
player -> "@p[tag=player]" # 定义绑定量（类似C语言的宏定义`#define`）
/tp ${player} 11 45 14
/execute at ${player} run setblock ~ ~ ~ grass
```

在 Acacia 中访问计分板的数值: `|"player": "scoreboard"| = 10`

## 了解更多
- [一个中文的介绍视频](https://www.bilibili.com/video/BV1uR4y167w9)
- 查看[这个测试文件](test/brief_intro.aca)来了解 Acacia 大概的语法。
- 在[这里](test/demo/numguess.aca)可以找到一个简单的猜数字demo!
