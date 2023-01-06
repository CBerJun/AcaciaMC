# Acacia
English | [中文](README_cn.md)

## Introduction
Acacia is a programming language for Minecraft (Bedrock) command development.
*Simple* is what Acacia wants. Minecraft commands can be complicated,
long and hard to maintain. Acacia simplify commands into Python-like
codes. Acacia code is finally compiled into mcfunction files, and can
be loaded in a Minecraft world as a datapack.

Go to [this test file](test/brief_intro.aca) for an overview of Acacia.

## Simple Code
Defining variables in Acacia: `a = 1`. That's it.
No need for scoreboards.

Nested expression within 1 line of code:
```
a = 10
# `10 + 20` is folded into `30`
b = (10 + 20) * a - 5
```

Functions:
```
def foo(x: int, y = True) -> int:
    pass # code here...
# These are all OK:
foo(1)
z = foo(2, False)
z = foo(x=3)
```

Builtin modules:
```
import print
money = 10
# Send "Hello, world!" in char to everyone
print.tell("Hello world!")
# Show "Money: (Value of variable `money`)" on actionbar to everyone
print.title(print.format("Money: %0", money), mode=print.ACTIONBAR)
```

## Compatible with Commands
Acacia supports commands inserted in code:
```
a = 1
/tp @p 11 45 14
/*
    tellraw @a {
    ...
    }
*/ # Multi-line command!
```

It can even simplify commands:
```
player -> "@p[tag=player]" # defining macro
/tp ${player} 11 45 14
/execute at ${player} run setblock ~ ~ ~ grass
```

Accessing scores on scoreboard: `|"player": "scoreboard"| = 10`

## Discover More about Acacia
- [An introduction video in Chinese](https://www.bilibili.com/video/BV1uR4y167w9)
- Go to [this test file](test/brief_intro.aca) for more details about Acacia!
- A simple number guessing game written in Acacia can also be found [here](test/demo/numguess.aca)!
