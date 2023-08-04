# Acacia
English | [中文](README_cn.md)

## Introduction
Acacia is a programming language for Minecraft Bedrock Edition command
development. Our principle is to be **as simple as possible**. Minecraft
commands can be complicated, long and hard to maintain. Acacia simplify
commands into Python-like code. Acacia code is finally compiled into
`.mcfunction` files, and can be loaded in a Minecraft world as a datapack.

Acacia is written in Python, so Python (require 3.6 or newer) is needed
for the compiler to run. It is also possible to create a binary module
using Python for Acacia code to use. For example, noteblock musics can
be generated automatically using builtin module `music`.

Go to [this test file](test/brief.aca) for an overview of Acacia.

## Simple Syntax
This is how to define a variable in Acacia: `a = 1`. That's it.
No need for scoreboards.

Nested expressions within 1 line of code:
```
a = 10
# `10 + 20` is folded into `30`
b = (10 + 20) * a - 5
```

Function definitions:
```
def foo(x: int, y = True) -> int:
    pass  # code here...
# These are all OK:
foo(1)
z = foo(2, False)
z = foo(x=3)
```

Flow control statements:
```
def is_prime(x: int) -> bool:
    #* Test if `x` is a prime number *#
    mod = 2
    result = True
    while mod <= x / 2:
        if x % mod == 0:
            result = False
        mod += 1
```

Various builtin modules:
```
import print
money = 10
# Send "Hello, world!" in chat to everyone
print.tell("Hello world!")
# Show "Money: (Value of variable `money`)" on actionbar to everyone
print.title(print.format("Money: %0", money), mode=print.ACTIONBAR)
```
```
import music
# Generate a noteblock music and use 1.2x speed.
m -> music.Music("music_score.mid", speed=1.2)
m.play()
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
*/  # Multi-line command!
```

It can even simplify commands:
```
player -> "@p[tag=player]"  # binding
/tp ${player} 11 45 14
/execute at ${player} run setblock ~ ~ ~ grass
```

Accessing scores on scoreboard: `|"player": "scoreboard"| = 10`

## Optimized Output
Acacia can even do better than you in some aspects like doing math!
```
def sum_between(start: int, to: int, delta=1) -> int:
    #* Return sum of Equidistant sequence from `start` to `to` with `delta` *#
    result = (start + to) * ((to - start) / delta + 1) / 2
sum_between(-5, 5, delta=2)
```

These commands are generated for function `sum_between`:
```mcfunction
# Set constants on initial run
scoreboard players set "acacia5" "acacia" 2
```
```mcfunction
# "acacia1", "acacia2" and "acacia3" are the arguments
# "acacia4" is result value
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
The order of the operations are well-organized by Acacia compiler.

## Discover More about Acacia
- [An introduction video in Chinese](https://www.bilibili.com/video/BV1uR4y167w9)
- [Use Acacia to generate noteblock musics](https://www.bilibili.com/video/BV1f24y1L7DB)
- Go to [this test file](test/brief.aca) for more details about Acacia!
- A simple number guessing game written in Acacia can also be found [here](test/demo/numguess.aca)!
