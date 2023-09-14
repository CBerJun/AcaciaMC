"""print - String formatting and printing module."""

from typing import List, Optional, TYPE_CHECKING
from copy import deepcopy

from acaciamc.mccmdgen.expression import *
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.error import *
from acaciamc.tools import axe, resultlib
import acaciamc.mccmdgen.cmds as cmds

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.mcselector import MCSelector

class ArgFString(axe.Multityped):
    """Accepts an fstring as argument. A string is also accepted and
    converted to an fstring.
    """
    def __init__(self):
        super().__init__((StringDataType, FStringDataType))

    def convert(self, origin: AcaciaExpr) -> "FString":
        origin = super().convert(origin)
        if isinstance(origin, String):
            fstr = FString([], [], origin.compiler)
            fstr.add_text(origin.value)
        else:
            assert isinstance(origin, FString)
            fstr = origin
        return fstr

class _FStrError(Exception):
    def __str__(self):
        return self.args[0]

class _FStrParser:
    def __init__(self, pattern: str, args, keywords):
        """Parse an fstring with `pattern` and `args` and `keywords`
        as formatted expressions."""
        self.pattern = pattern
        self.args = args
        self.keywords = keywords
        self.dependencies = []
        self.json = []  # the result

    def next_char(self) -> str:
        """Move to next char."""
        if not self.pattern:
            return None
        ret = self.pattern[0]
        self.pattern = self.pattern[1:]
        return ret

    def add_text(self, text: str):
        # if the last component in json is text, too,
        # we add these text to it
        if bool(self.json) and self.json[-1].get('text'):
            self.json[-1]['text'] += text
        else:  # fallback
            self.json.append({"text": text})

    def add_score(self, slot: cmds.ScbSlot):
        self.json.append({
            "score": {"objective": slot.objective, "name": slot.target}
        })

    def add_expr(self, expr: AcaciaExpr):
        """Format an expression to string."""
        if expr.data_type.matches_cls(IntDataType):
            if isinstance(expr, IntLiteral):
                # optimize for literals
                self.add_text(str(expr.value))
            else:
                dependencies, var = to_IntVar(expr)
                self.dependencies.extend(dependencies)
                self.add_score(var.slot)
        elif expr.data_type.matches_cls(BoolDataType):
            if isinstance(expr, BoolLiteral):
                # optimize for literals
                self.add_text('1' if expr.value else '0')
            else:
                dependencies, var = to_BoolVar(expr)
                self.dependencies.extend(dependencies)
                self.add_score(var.slot)
        elif isinstance(expr, String):
            self.add_text(expr.value)
        elif isinstance(expr, FString):
            self.json.extend(expr.json)
        else:
            raise _FStrError('Type "%s" can not be formatted as a string'
                             % expr.data_type)

    def expr_from_id(self, name: str) -> AcaciaExpr:
        """Get the expr from an format
        e.g. "0" -> args[0]; "key" -> keywords["key"]
        """
        if name.isdecimal():
            index = int(name)
            try:
                expr = self.args[index]
            except IndexError:
                raise _FStrError('Format index out of range: %d' % index)
        elif name in self.keywords:
            expr = self.keywords[name]
        else:
            raise _FStrError('Invalid format expression: %r' % name)
        return expr

    def parse(self):
        char = ''
        while True:
            char = self.next_char()
            if char is None:
                break
            # Normal char
            if char != '%':
                self.add_text(char)
                continue
            # % format
            second = self.next_char()
            if second == '%' or second is None:
                # '%%' escape -> '%' OR '%' at the end of string
                self.add_text('%')
                continue
            # 1. Parse which expression is being used here
            if second == '{':
                # read until }
                expr_str = ''
                expr_char = self.next_char()
                while expr_char != '}':
                    if expr_char is None:
                        raise _FStrError('Unclosed "{" in fstring')
                    expr_str += expr_char
                    expr_char = self.next_char()
                # expr is integer or an identifier
                expr = self.expr_from_id(expr_str)
            elif second.isdecimal():
                # %1 is the alias to %{1}
                expr = self.expr_from_id(second)
            else:
                # can't be understood, just use raw text
                self.add_text(char + second)
                continue
            # 3. Handle the `expr` we got
            self.add_expr(expr)
        return self.dependencies, self.json

class FStringDataType(DefaultDataType):
    name = 'fstring'

class FString(AcaciaExpr):
    """A formatted string in JSON format."""
    def __init__(self, dependencies: List[str], json: List[dict], compiler):
        # dependencies: commands to run before json rawtext is used
        # json: JSON rawtext without {"rawtext": ...}
        super().__init__(FStringDataType(), compiler)
        self.dependencies = dependencies
        self.json = json

    def add_text(self, text: str):
        # add text to fstring
        if bool(self.json) and self.json[-1].get('text'):
            self.json[-1]['text'] += text
        else:  # fallback
            self.json.append({"text": text})

    def copy(self):
        return FString(self.dependencies.copy(),
                       deepcopy(self.json), self.compiler)

    def __add__(self, other):
        # connect strings
        res = self.copy()
        if isinstance(other, String):
            res.add_text(other.value)
        elif isinstance(other, FString):
            # connect json
            res.json.extend(other.json)
        else:
            return NotImplemented
        return res

    def __radd__(self, other):
        return self.__add__(other)

### Functions ###

## For creating strings

@axe.chop
@axe.arg("_pattern", axe.LiteralString(), rename="pattern")
@axe.star_arg("args", axe.AnyValue())
@axe.kwds("kwds", axe.AnyValue())
def _format(compiler, pattern: str, args, kwds):
    """
    format(_pattern: str, *args, **kwargs)

    Formatted string type.
    So far, `args` and `kwargs` may be int, bool, str and fstring
    NOTE Booleans are formatted as "0" and "1".
    in _pattern:
     "%%" -> character "%"
     "%{" integer "}" -> args[integer]
     "%" one-digit-number -> alias to `"%{" one-digit-number "}"`
     "%{" id "}" -> kwargs[id] (id is an valid Acacia identifier)
    Examples:
     format("Val1: %0; Val2: %{value}; Name: %{1}", val1, x, value=val2)
    """
    try:
        dependencies, json = _FStrParser(pattern, args, kwds).parse()
    except _FStrError as err:
        raise Error(ErrorType.ANY, message=str(err))
    # scan pattern
    return FString(dependencies, json, compiler)

@axe.chop
@axe.arg("key", axe.LiteralString())
def _translate(compiler, key: str):
    """
    Return an fstring that uses the given localization key.
    Example: format("Give me %0!", translate("item.diamond.name"))
    """
    return FString([], [{"translate": key}], compiler)

## For printing

@axe.chop
@axe.arg("text", ArgFString())
@axe.arg("target", axe.PlayerSelector(), default=None)
def _tell(compiler, text: FString, target: Optional["MCSelector"]):
    """tell(text: str | fstring, target: PlayerSelector = <All players>)
    Tell the `target` the `text` using /tellraw.
    """
    commands = []
    if target is None:
        target_str = "@a"
    else:
        target_str = target.to_str()
    commands.extend(text.dependencies)
    commands.append(cmds.RawtextOutput("tellraw %s" % target_str, text.json))
    return resultlib.commands(commands, compiler)

# Title modes
_TITLE = 'title'
_SUBTITLE = 'subtitle'
_ACTIONBAR = 'actionbar'
# Default configurations
_FADE_IN = 10
_STAY_TIME = 70
_FADE_OUT = 20
_DEF_TITLE_CONFIG = (_FADE_IN, _STAY_TIME, _FADE_OUT)

@axe.chop
@axe.arg("text", ArgFString())
@axe.arg("target", axe.PlayerSelector(), default=None)
@axe.arg("mode", axe.LiteralString(), default=_TITLE)
@axe.arg("fade_in", axe.LiteralInt(), default=_FADE_IN)
@axe.arg("stay_time", axe.LiteralInt(), default=_STAY_TIME)
@axe.arg("fade_out", axe.LiteralInt(), default=_FADE_OUT)
def _title(compiler, text: FString, target: Optional["MCSelector"], mode: str,
           fade_in: int, stay_time: int, fade_out: int):
    """title(
        text: str | fstring,
        target: PlayerSelector = <All players>,
        mode: str = TITLE,
        fade_in: int-literal = 10,
        stay_time: int-literal = 70,
        fade_out: int-literal = 20
    )
    Use /titleraw for showing `text`.
    `fade_in`, `stay_time` and `fade_out` are in ticks.
    """
    commands = []
    # Check valid mode
    if mode not in (_TITLE, _SUBTITLE, _ACTIONBAR):
        raise axe.ArgumentError('mode', 'invalid mode: %s' % mode)
    if target is None:
        target_str = "@a"
    else:
        target_str = target.to_str()
    # Start
    ## set config
    conf = (fade_in, stay_time, fade_out)
    if conf != _DEF_TITLE_CONFIG:
        # only set config when it's not the default one
        commands.append(cmds.TitlerawTimes(target_str, *conf))
    ## titleraw
    commands.extend(text.dependencies)
    commands.append(
        cmds.RawtextOutput('titleraw %s %s' % (target_str, mode), text.json)
    )
    ## reset config
    if conf != _DEF_TITLE_CONFIG:
        # only reset when config is not the default one
        commands.append(cmds.TitlerawResetTimes(target_str))
    ## return
    return resultlib.commands(commands, compiler)

@axe.chop
@axe.arg("target", axe.PlayerSelector(), default=None)
def _title_clear(compiler, target: Optional["MCSelector"]):
    """title_clear(target: PlayerSelector = <All players>)
    Clear `target`'s title text.
    """
    if target is None:
        target_str = "@a"
    else:
        target_str = target.to_str()
    return resultlib.commands([cmds.TitlerawClear(target_str)], compiler)

def acacia_build(compiler: "Compiler"):
    return {
        'format': BinaryFunction(_format, compiler),
        'translate': BinaryFunction(_translate, compiler),
        'tell': BinaryFunction(_tell, compiler),
        'title': BinaryFunction(_title, compiler),
        'TITLE': String(_TITLE, compiler),
        'SUBTITLE': String(_SUBTITLE, compiler),
        'ACTIONBAR': String(_ACTIONBAR, compiler),
        'title_clear': BinaryFunction(_title_clear, compiler)
    }
