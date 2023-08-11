# Acacia
English | [中文](README_cn.md)

## Introduction
**Acacia is a programming language that runs in Minecraft Bedrock Edition.**
Minecraft commands can be complicated, long and hard to maintain.
Acacia is an alternative to commands -- it is also used to control Minecraft.
*However*, Acacia code is much more readable than commands, which increases the maintainability of your project and your productivity.
**Imagine writing a Tetris game that runs in Minecraft using less than 14KB code** (see [below](#what-can-acacia-do))!

Acacia code is finally compiled into `.mcfunction` files.
In other word, Acacia code will be converted into Minecraft commands by the program, and can be loaded in a Minecraft world as a behavior pack.

Still confused? Here's a simple Acacia program that calculates sum of elements in an arithmetic sequence in Minecraft:
```
import print
def sum_between(start: int, to: int, delta=1) -> int:
    #*
    Return sum of arithmetic sequence that starts with `start`,
    ends with `to` with common difference `delta`.
    *#
    result = (start + to) * ((to - start) / delta + 1) / 2
res = sum_between(-5, 5, delta=2)
print.tell(print.format("Sum of arithmetic sequence (-5~5, d=2) is %0", res))
```
It will be converted to commands by compiler (the program in this repository):
```mcfunction
scoreboard players set "acacia1" "acacia" -5
scoreboard players set "acacia2" "acacia" 5
scoreboard players set "acacia3" "acacia" 2
function acacia/lib/acalib1
scoreboard players operation "acacia9" "acacia" = "acacia4" "acacia"
tellraw @a {"rawtext": [{"text": "Sum of arithmetic sequence (-5~5, d=2) is "}, {"score": {"objective": "acacia", "name": "acacia9"}}]}
```
```mcfunction
# Set constants on initial run
scoreboard players set "acacia5" "acacia" 2
```
```mcfunction
## This is acacia/lib/acalib1.mcfunction
# "acacia1", "acacia2" and "acacia3" are start, to and delta respectively.
# "acacia4" is result.
scoreboard players operation "acacia8" "acacia" = "acacia2" "acacia"
scoreboard players operation "acacia8" "acacia" -= "acacia1" "acacia"
scoreboard players operation "acacia8" "acacia" /= "acacia3" "acacia"
scoreboard players add "acacia8" "acacia" 1
scoreboard players operation "acacia7" "acacia" = "acacia8" "acacia"
scoreboard players operation "acacia6" "acacia" = "acacia1" "acacia"
scoreboard players operation "acacia6" "acacia" += "acacia2" "acacia"
scoreboard players operation "acacia6" "acacia" *= "acacia7" "acacia"
scoreboard players operation "acacia6" "acacia" /= "acacia5" "acacia"
scoreboard players operation "acacia4" "acacia" = "acacia6" "acacia"
```
Running this program will send this message in Minecraft's chat:
> Sum of arithmetic sequence (-5~5, d=2) is 0

Acacia is written in Python, so Python (3.6 or newer) is required by compiler.

## What can Acacia do?
Some real-world examples:
- **Without writing 1 command**, we can create a simple Tetris game in Minecraft!
  The source code can be found [here](test/demo/tetris.aca).
  It is only 14KB in size! The generated command, however, uses more than 400KB.
- Noteblock musics can be automatically generated by the builtin module `music`.

Detailed features:
- No more redundant commands and huge amount of files; Acacia code is simple.
- No more worries about `/execute` context.
- No more entity tags; Acacia has an exclusive entity system!
- No more scoreboards! Instead we have the variable system which is popular in computer programming.
- No more repetitive commands; Acacia is good at generating repetitive commands.
- You can define loops and use the "if" statement to run something conditionally.
- Acacia provides various constants, including numbers, strings, arrays, maps and even world positions.
  This makes your map or addon more flexible.

Check out [this file](test/brief.aca) for more information about Acacia's syntax.

## Syntax Overview
This is how to define a variable in Acacia: `a = 1`. That's it.
No need for scoreboards.

Nested expressions within 1 line of code:
```python
a = 10
b = (10 + a) * a - 5
```

Function definitions:
```python
def foo(x: int, y = True) -> int:
    pass  # code here...
# These are all OK:
foo(1)
z = foo(2, False)
z = foo(x=3)
```

Flow control statements (selections and loops):
```python
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
```python
import print
money = 10
# Send "Hello, world!" in chat to everyone
print.tell("Hello world!")
# Show "Money: (Value of variable `money`)" on actionbar to everyone
print.title(print.format("Money: %0", money), mode=print.ACTIONBAR)
```
```python
import music
# Generate a noteblock music and use 1.2x speed.
m -> music.Music("music_score.mid", speed=1.2)
m.play()
```

Use of constants and power to generate repetitive code:
```python
COLORS -> {
    0: "cyan", 1: "orange", 2: "yellow",
    3: "purple", 4: "lime", 5: "red", 6: "blue"
}
i = 0  # Calculate `i`...
for c in COLORS:
    if c == i:
        world.setblock(
            Pos(0, -50, 0),
            world.Block("concrete", {"color": COLORS.get(c)})
        )
```

Position and entity system:
```python
import world

ORIGIN -> Pos(0, -50, 0)
world.fill(ORIGIN, Offset().offset(x=5, z=5), world.Block("air"))

entity Test:
    @type: "armor_stand"
    @position: ORIGIN

    def __init__():
        world.setblock(Pos(self), world.Block("diamond_block"))
        world.effect_give(self, "invisibility")

    def foo():
        world.tp(self, ORIGIN)

test_group -> Engroup(Test)
test_group.select(Enfilter().distance_from(ORIGIN, max=5))
for entity test in test_group:
    test.foo()
```

## Discover More about Acacia
- [An introduction video in Chinese](https://www.bilibili.com/video/BV1uR4y167w9)
- [Use Acacia to generate noteblock musics](https://www.bilibili.com/video/BV1f24y1L7DB)
- Go to [this test file](test/brief.aca) for more details about Acacia!
- A simple Guess the Number game written in Acacia can also be found [here](test/demo/numguess.aca)!
