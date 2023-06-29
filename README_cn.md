# Acacia
[English](README.md) | 中文

## 简介
Acacia 是一门为 Minecraft 基岩版指令开发设计的编程语言。
Acacia 的原则是**尽可能简单**。Minecraft 的命令较为复杂、很长、且难以维护。
Acacia 将指令简化为了类似 Python 语言的代码。
代码最终会被编译为多个 `.mcfunction` 文件，可以通过数据包被加载进一个世界。

Acacia 是使用 Python 编写的，所以编译器需要 Python（需要 3.5 或以上版本）来运行。
通过 Python 也可以创建可供 Acacia 调用的模块。例如，通过内置模块 `music` 可以
自动生成红石音乐。

查看[这个文件](test/brief.aca)来了解 Acacia 大概的语法。

## 简单的语法
这是在 Acacia 中定义变量的方法: `a = 1`。
就这么简单捏，无需研究计分板系统了。

一行代码计算复杂的表达式:
```
a = 10
# `10 + 20` 会被编译器折叠为 `30`
b = (10 + 20) * a - 5
```

定义函数:
```
def foo(x: int, y = True) -> int:
    pass  # 这里写函数体代码
# 下面这些都是合法的调用:
foo(1)
z = foo(2, False)
z = foo(x=3)
```

控制语句:
```
def is_prime(x: int) -> bool:
    #* 检测`x`是不是质数 *#
    mod = 2
    result True
    while mod <= x / 2:
        if x % mod == 0:
            result False
        mod += 1
```

丰富的内置模块:
```
import print
money = 10
# 在聊天栏向所有人输出"Hello, world!"
print.tell("Hello world!")
# 在所有玩家的快捷栏上方显示"Money: (money变量的数值)"
print.title(print.format("Money: %0", money), mode=print.ACTIONBAR)
```
```
import music
# 自动生成红石音乐，并采用1.2倍速。
m -> music.Music("music_score.mid", speed=120)
m.play()
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
*/  # 多行命令!
```

它甚至能够帮你简化命令:
```
player -> "@p[tag=player]"  # 定义绑定量
/tp ${player} 11 45 14
/execute at ${player} run setblock ~ ~ ~ grass
```

在 Acacia 中访问计分板的数值: `|"player": "scoreboard"| = 10`

## 输出优化
在数字计算方面等方面，Acacia 甚至比你都能做得更好!
```
def sum_between(start: int, to: int, delta=1) -> int:
    #* 返回以`start`为首项，`to`为末项，`delta`为公差的等差数列的和 *#
    result (start + to) * ((to - start) / delta + 1) / 2
sum_between(-5, 5, delta=2)
```

下面是为 `sum_between` 函数生成的命令:
```mcfunction
# 第一次运行时设置常量
scoreboard players set "acacia5" "acacia" 2
```
```mcfunction
# "acacia1"，"acacia2" 和 "acacia3" 都是函数的参数
# "acacia4" 是函数返回值
scoreboard players operation "acacia5" "acacia" = "acacia2" "acacia"
scoreboard players operation "acacia5" "acacia" -= "acacia1" "acacia"
scoreboard players operation "acacia5" "acacia" /= "acacia3" "acacia"
scoreboard players add "acacia5" "acacia" 1
scoreboard players operation "acacia7" "acacia" = "acacia5" "acacia"
scoreboard players operation "acacia6" "acacia" = "acacia1" "acacia"
scoreboard players operation "acacia6" "acacia" += "acacia2" "acacia"
scoreboard players operation "acacia6" "acacia" *= "acacia7" "acacia"
scoreboard players operation "acacia6" "acacia" /= "acacia5" "acacia"
scoreboard players operation "acacia4" "acacia" = "acacia6" "acacia"
```
这些运算的顺序都被 Acacia 安排得妥妥的。

## 了解更多
- [一个中文的介绍视频](https://www.bilibili.com/video/BV1uR4y167w9)
- [用 Acacia 生成红石音乐](https://www.bilibili.com/video/BV1f24y1L7DB)
- 查看[这个测试文件](test/brief.aca)来了解 Acacia 大概的语法。
- 在[这里](test/demo/numguess.aca)可以找到一个简单的猜数字demo!
