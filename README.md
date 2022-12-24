# Acacia
Acacia is a programming language for Minecraft (Bedrock) development
*Simple* is what Acacia wants. Minecraft commands can be complicated,
long and hard to maintain. Acacia simplify commands into Python-like
codes. Acacia code is finally compiled into mcfunction files, and can
be loaded in a Minecraft world as a datapack.
Check out test/brief_intro.aca for a simple tutorial on Acacia.

## Simple Code
Defining variables in Acacia: `a = 1`. That's it. No need for scoreboards.
Defining functions:
```
    def foo(x: int, y = True) -> int:
        pass # code here...
```
Builtin modules:
```
    import print
    money = 10
    print.tell("Hello world!")
    print.title(print.format("Money: %0", money), mode=print.ACTIONBAR)
```

## Compatible with Commands
Acacia supports commands inserted in Acacia:
```
    a = 1
    /tp @p 11 45 14
```
Accessing scores on scoreboard: `|"player": "scoreboard"|`

## Discover More about Acacia
See `test/brief_intro.aca` for more details about Acacia!
A number guessing game written in Acacia can be found in `test/demo/numguess.aca`!
