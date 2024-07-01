"""print - String formatting and printing module."""

from string import digits as DIGITS
from typing import List, Optional, Tuple, TYPE_CHECKING

import acaciamc.mccmdgen.cmds as cmds
from acaciamc.constants import COLORS, COLORS_NEW
from acaciamc.error import *
from acaciamc.localization import localize
from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.utils import InvalidOpError
from acaciamc.objects import *
from acaciamc.tools import axe, resultlib

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
            fstr = FString([], [cmds.RawtextText(origin.value)])
        else:
            assert isinstance(origin, FString)
            fstr = origin
        return fstr


class _FStrError(Exception):
    def __str__(self):
        return self.args[0]


class _FStrParser:
    def __init__(self, pattern: str, args, keywords, compiler: "Compiler"):
        """Parse an fstring with `pattern` and `args` and `keywords`
        as formatted expressions."""
        self.pattern = pattern
        self.ptr = 0
        self.args = args
        self.keywords = keywords
        self.compiler = compiler
        self.dependencies = []
        self.rawtext = cmds.Rawtext()

    def next_char(self) -> Optional[str]:
        """Move to next char."""
        if self.ptr >= len(self.pattern):
            return None
        c = self.pattern[self.ptr]
        self.ptr += 1
        return c

    def add_text(self, text: str):
        self.rawtext.append(cmds.RawtextText(text))

    def add_expr(self, expr: AcaciaExpr):
        """Format an expression to string."""
        try:
            components, deps = expr.rawtextify(self.compiler)
        except InvalidOpError:
            raise _FStrError(
                localize("modules.print.fstr.addexpr.error")
                % expr.data_type
            )
        else:
            self.rawtext.extend(components)
            self.dependencies.extend(deps)

    def expr_from_id(self, name: str) -> AcaciaExpr:
        """Get the expr from an format
        e.g. "0" -> args[0]; "key" -> keywords["key"]
        """
        if all(c in DIGITS for c in name):
            index = int(name)
            try:
                expr = self.args[index]
            except IndexError:
                raise _FStrError(
                    localize("modules.print.fstr.exprfromid.outofrange")
                    % index
                )
        elif name in self.keywords:
            expr = self.keywords[name]
        else:
            raise _FStrError(
                localize('modules.print.fstr.exprfromid.invalid') % name
            )
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
                expr_str = []
                expr_char = self.next_char()
                while expr_char != '}':
                    if expr_char is None:
                        raise _FStrError(
                            localize("modules.print.fstr.parse.unclosedbrace")
                        )
                    expr_str.append(expr_char)
                    expr_char = self.next_char()
                # expr is integer or an identifier
                expr = self.expr_from_id(''.join(expr_str))
            elif second in DIGITS:
                # %1 is the alias to %{1}
                expr = self.expr_from_id(second)
            else:
                # can't be understood, just use raw text
                self.add_text(char + second)
                continue
            # 3. Handle the `expr` we got
            self.add_expr(expr)
        return self.dependencies, self.rawtext


class FStringDataType(DefaultDataType):
    name = 'fstring'


ctdt_fstring = CTDataType("fstring")


class FString(ConstExprCombined):
    """A formatted string in JSON format."""
    cdata_type = ctdt_fstring

    def __init__(self, dependencies: List[str],
                 components: List[cmds.RawtextComponent]):
        """
        dependencies: commands to run before json rawtext is used
        components: rawtext components
        """
        super().__init__(FStringDataType())
        self.dependencies = dependencies
        self.rawtext = cmds.Rawtext(components)

    def rawtextify(self, compiler):
        return self.rawtext, self.dependencies

    def copy(self):
        return FString(self.dependencies.copy(), self.rawtext.copy())

    def cadd(self, other):
        """Concatenate formatted strings."""
        res = self.copy()
        if isinstance(other, String):
            res.rawtext.append(cmds.RawtextText(other.value))
        elif isinstance(other, FString):
            res.rawtext.extend(other.rawtext)
        else:
            raise InvalidOpError
        return res

    def cradd(self, other):
        # Only normal strings can be `other`, since if they are fstrings
        # `cadd` would have handled it.
        res = self.copy()
        if isinstance(other, String):
            res.rawtext.insert(0, cmds.RawtextText(other.value))
        else:
            raise InvalidOpError
        return res


### Functions ###

## For creating strings

@axe.chop
@axe.arg("_pattern", axe.LiteralString(), rename="pattern")
@axe.star_arg("args", axe.AnyRT())
@axe.kwds("kwds", axe.AnyRT())
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
        dependencies, rawtext = \
            _FStrParser(pattern, args, kwds, compiler).parse()
    except _FStrError as err:
        raise Error(ErrorType.ANY, message=str(err))
    return FString(dependencies, rawtext)


@axe.chop
@axe.arg("key", axe.LiteralString())
def _translate(compiler, key: str):
    """
    Return an fstring that uses the given localization key.
    Example: format("Give me %0!", translate("item.diamond.name"))
    """
    return FString([], [cmds.RawtextTranslate(key)])


class _FontComponent(cmds.RawtextText):
    """A utility component used by `with_font`."""

    def __init__(self, text: str, label: str):
        super().__init__(text)
        self.label = label


COLOR_DEFAULT = "default"


@axe.chop
@axe.arg("text", ArgFString())
@axe.arg("color", axe.LiteralStringEnum(*COLORS, *COLORS_NEW, COLOR_DEFAULT),
         default=COLOR_DEFAULT)
@axe.arg("bold", axe.LiteralBool(), default=False)
@axe.arg("italic", axe.LiteralBool(), default=False)
@axe.arg("obfuscated", axe.LiteralBool(), default=False)
def _with_font(compiler: "Compiler", text: FString, color: str,
               bold: bool, italic: bool, obfuscated: bool):
    """
    with_font(
        text: str | fstring,
        color: str = "default",
        bold: bool-literal = False,
        italic: bool-literal = False,
        obfuscated: bool-literal = False
    ) -> fstring
    Return an fstring that has the given color and font when displayed.
    When uses of this function are embedded, for example:
        with_font(
            format("Hello %0!", with_font("world", "red", bold=True)),
            color="green"
        )
    The inner `with_font` has higher priority, so the result is:
        "Hello " (green) + "world" (red, bold) + "!" (green)
    When this function is used, it is not recommended to use formatting
    code (\u00A7, section sign; \# escape in Acacia) manually.
    """
    if color in COLORS_NEW and compiler.cfg.mc_version < (1, 19, 80):
        raise axe.ArgumentError(
            "color", localize("modules.print.withfont.onlyhighversion") % color
        )
    res = text.copy()
    fmts = []
    if color != COLOR_DEFAULT:
        if color in COLORS_NEW:
            color_str = COLORS_NEW[color]
        else:
            color_str = COLORS[color]
        fmts.append("\xA7" + color_str)
    if bold:
        fmts.append("\xA7l")
    if italic:
        fmts.append("\xA7o")
    if obfuscated:
        fmts.append("\xA7k")
    scopes: List[Tuple[int, int]] = []  # [start, end)
    start_i = 0
    start_levels = 0
    length = len(res.rawtext)
    for i, component in enumerate(res.rawtext):
        if isinstance(component, _FontComponent):
            if component.label == "start":
                start_levels += 1
                if start_levels == 1 and i > start_i:
                    scopes.append((start_i, i))
                    start_i = -1
            if component.label == "end":
                start_levels -= 1
                if start_levels == 0 and i != length - 1:
                    start_i = i + 1
    if start_levels:
        raise ValueError("Unclosed font scopes")
    if start_i != -1:
        scopes.append((start_i, length))
    scopes.reverse()
    fmt_code = "".join(fmts)
    for start_i, end_i in scopes:
        res.rawtext.insert(end_i, _FontComponent("\xA7r", "end"))
        res.rawtext.insert(start_i, _FontComponent(fmt_code, "start"))
    return res


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
    commands.append(cmds.RawtextOutput(f"tellraw {target_str}", text.rawtext))
    return resultlib.commands(commands)


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
@axe.arg("mode", axe.LiteralStringEnum(_TITLE, _SUBTITLE, _ACTIONBAR),
         default=_TITLE)
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
        cmds.RawtextOutput(f'titleraw {target_str} {mode}', text.rawtext)
    )
    ## reset config
    if conf != _DEF_TITLE_CONFIG:
        # only reset when config is not the default one
        commands.append(cmds.TitlerawResetTimes(target_str))
    ## return
    return resultlib.commands(commands)


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
    return resultlib.commands([cmds.TitlerawClear(target_str)])


def acacia_build(compiler: "Compiler"):
    return {
        'format': BinaryCTFunction(_format),
        'translate': BinaryCTFunction(_translate),
        'with_font': BinaryCTFunction(_with_font),
        'tell': BinaryFunction(_tell),
        'title': BinaryFunction(_title),
        'TITLE': String(_TITLE),
        'SUBTITLE': String(_SUBTITLE),
        'ACTIONBAR': String(_ACTIONBAR),
        'title_clear': BinaryFunction(_title_clear)
    }
