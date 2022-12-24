# Builtin string formatting and printing module for Acacia
from acaciamc.mccmdgen.expression import *
from acaciamc.error import *

from copy import deepcopy
import json

# FString

class _FStrParseError(Exception):
    def __str__(self):
        return self.args[0]

class _FStrParser:
    def __init__(self, pattern: str, args, keywords):
        # parse an fstring with `pattern` and `args` and `keywords`
        # as formatted expressions
        self.pattern = pattern
        self.args = args
        self.keywords = keywords
        self.dependencies = []
        self.json = [] # the result
    
    def next_char(self) -> str:
        # move to next char
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
        else: # fallback
            self.json.append({"text": text})
    
    def add_score(self, objective: str, selector: str):
        self.json.append({
            "score": {"objective": objective, "name": selector}
        })
    
    def add_expr(self, expr: AcaciaExpr):
        # add an expr to string
        if isinstance(expr.type, BuiltinIntType):
            if isinstance(expr, IntLiteral):
                # optimize for literals
                self.add_text(str(expr.value))
                return
            dependencies, var = to_IntVar(expr)
        elif isinstance(expr.type, BuiltinBoolType):
            if isinstance(expr, BoolLiteral):
                # optimize for literals
                self.add_text('1' if expr.value else '0')
                return
            dependencies, var = to_BoolVar(expr)
        else:
            raise _FStrParseError(
                'Type "%s" is not supported in fstring' % expr.type.name
            )
        self.dependencies.extend(dependencies)
        self.add_score(var.objective, var.selector)
    
    def expr_from_id(self, name: str) -> AcaciaExpr:
        # get the expr from an format
        # e.g. "0" -> args[0]; "key" -> keywords["key"]
        if name.isdecimal():
            index = int(name)
            try:
                expr = self.args[index]
            except IndexError:
                raise _FStrParseError('Format index out of range: %d' % index)
        elif name in self.keywords:
            expr = self.keywords[name]
        else:
            raise _FStrParseError(
                'Invalid format expression: %r' % name
            )
        return expr
    
    def parse(self):
        char = self.next_char()
        while char is not None:
            # normal char
            if char != '%':
                self.add_text(char)
            else: # % format
                peek = self.next_char()
                if peek == '%':
                    # '%%' escape -> '%'
                    self.add_text('%')
                elif peek == '{':
                    # read until }
                    expr_str = ''
                    expr_char = self.next_char()
                    while expr_char != '}':
                        if expr_char is None:
                            raise _FStrParseError('Unclosed "{" in fstring')
                        expr_str += expr_char
                        expr_char = self.next_char()
                    # expr is integer or an identifier
                    expr = self.expr_from_id(expr_str)
                    # add expr
                    self.add_expr(expr)
                elif peek is None:
                    # if string ends at `char`, just use raw text
                    self.add_text(char)
                # NOTE isdecimal() branch is put after `is None` to make
                # sure `peek` is an str (rather than NoneType)
                elif peek.isdecimal():
                    # %1 is the alia to %{1}
                    expr = self.expr_from_id(peek)
                    self.add_expr(expr)
                else:
                    # can't be understood, just use raw text
                    self.add_text(char + peek)
            # read next
            char = self.next_char()
        return self.dependencies, self.json

class FStringType(Type):
    # formatted string type
    # format(_pattern: str, *args: int|bool, **kwargs: int|bool)
    # NOTE booleans are formatted as "0" and "1"
    # in _pattern:
    #  "%%" -> character "%"
    #  "%{" integer "}" -> args[integer]
    #  "%" one-digit -> alia to `"%{" one-digit "}"`
    #  "%{" id "}" -> kwargs[id] (id is an valid Acacia identifier)
    # e.g. format("Val1: %0; Val2: %{name}; Name: %{1}", val1, val2, name=x)
    name = 'fstring'

    def do_init(self):
        def _new(func: BinaryFunction):
            # constructor of fstring type
            arg_pattern = func.arg_require('_pattern', BuiltinStringType)
            arg_fargs, arg_fkws = func.arg_raw()
            try:
                dependencies, json = _FStrParser(
                    arg_pattern.value, arg_fargs, arg_fkws
                ).parse()
            except _FStrParseError as err:
                func.compiler.error(ErrorType.ANY, message = str(err))
            # scan pattern
            return FString(dependencies, json, func.compiler)
        self.attribute_table.create(
            '__new__', BinaryFunction(_new, self.compiler)
        )

class FString(AcaciaExpr):
    # an formatted string in JSON format
    def __init__(self, dependencies: list, json: list, compiler):
        # dependencies:list[str] commands ran before json rawtext
        # json:list JSON rawtext without {"rawtext": ...}
        super().__init__(compiler.types[FStringType], compiler)
        self.dependencies = dependencies
        self._json = json
    
    def export_json_str(self) -> str:
        return json.dumps({"rawtext": self._json})
    
    def add_text(self, text: str):
        # add text to fstring
        if bool(self._json) and self._json[-1].get('text'):
            self._json[-1]['text'] += text
        else: # fallback
            self._json.append({"text": text})
    
    def deepcopy(self):
        return FString(
            deepcopy(self.dependencies), deepcopy(self._json), self.compiler
        )
    
    def __add__(self, other):
        # connect strings
        res = self.deepcopy()
        if isinstance(other, String):
            res.add_text(other.value)
        elif isinstance(other, FString):
            # connect json
            res._json.extend(other._json)
        else: raise TypeError
        return res
    
    def __radd__(self, other):
        return self.__add__(other)

# output functions

def _tell(func: BinaryFunction):
    # tell(text: str|fstring, target: str = "@a") -> nonetype
    # tell the `target` the `text` using /tellraw
    # arg parse
    arg_text = func.arg_require('text', (BuiltinStringType, FStringType))
    ## convert str to fstring
    if isinstance(arg_text, String):
        arg_text = func.compiler.types[FStringType].call(
            args = (arg_text,), keywords = {}
        )
    arg_target = func.arg_optional(
        'target', String('@a', func.compiler), BuiltinStringType
    )
    func.assert_no_arg()
    # add to tellraw
    cmds = deepcopy(arg_text.dependencies)
    cmds.append('tellraw %s %s' % (
        arg_target.value, arg_text.export_json_str()
    ))
    return NoneCallResult(cmds, NoneVar(func.compiler), func.compiler)

# title modes
# NOTE these are just random numbers...
_TITLE = 'title'
_SUBTITLE = 'subtitle'
_ACTIONBAR = 'actionbar'
# Default configurations
_FADE_IN = 10
_STAY_TIME = 70
_FADE_OUT = 20
_DEF_TITLE_CONFIG = (_FADE_IN, _STAY_TIME, _FADE_OUT) # default config

def _title(func: BinaryFunction):
    # title(
    #   text: str|fstring, target: str = "@a", mode: str = TITLE,
    #   fade_in: int-literal, stay_time: int-literal, fade_out: int-literal
    # )
    # use /titleraw for output
    # fade_in, stay_time and fade_out are in ticks for configuring
    # arg parse
    arg_text = func.arg_require('text', (BuiltinStringType, FStringType))
    arg_target = func.arg_optional(
        'target', String('@a', func.compiler), BuiltinStringType
    )
    arg_mode = func.arg_optional(
        'mode', String(_TITLE, func.compiler), BuiltinStringType
    )
    arg_fade_in = func.arg_optional(
        'fade_in', IntLiteral(_FADE_IN, func.compiler), BuiltinIntType
    )
    arg_stay_time = func.arg_optional(
        'stay_time', IntLiteral(_STAY_TIME, func.compiler), BuiltinIntType
    )
    arg_fade_out = func.arg_optional(
        'fade_out', IntLiteral(_FADE_OUT, func.compiler), BuiltinIntType
    )
    func.assert_no_arg()
    ## convert str to fstring
    if isinstance(arg_text, String):
        arg_text = func.compiler.types[FStringType].call(
            args = (arg_text,), keywords = {}
        )
    ## check arg int literal
    if not isinstance(arg_fade_in, IntLiteral):
        func.arg_error('fade_in', 'should be a literal')
    if not isinstance(arg_stay_time, IntLiteral):
        func.arg_error('stay_time', 'should be a literal')
    if not isinstance(arg_fade_out, IntLiteral):
        func.arg_error('fade_out', 'should be a literal')
    ## check valid mode
    mode = arg_mode.value
    if mode not in (_TITLE, _SUBTITLE, _ACTIONBAR):
        func.arg_error('mode', 'invalid mode: %s' % mode)
    # Start
    res = []
    ## set config
    target = arg_target.value
    conf = (arg_fade_in.value, arg_stay_time.value, arg_fade_out.value)
    if conf != _DEF_TITLE_CONFIG:
        # only set config when it's not the default one
        res.append('titleraw %s times %d %d %d' % ((target,) + conf))
    ## titleraw
    res.extend(arg_text.dependencies)
    res.append('titleraw %s %s %s' % (
        target, mode, arg_text.export_json_str()
    ))
    ## reset config
    if conf != _DEF_TITLE_CONFIG:
        # only reset when config is not the default one
        res.append('titleraw %s reset' % target)
    ## return
    return NoneCallResult(res, NoneVar(func.compiler), func.compiler)

def _title_clear(func: BinaryFunction):
    # title_clear(target: str = "@a")
    # Parse arg
    arg_target = func.arg_optional(
        'target', String('@a', func.compiler), BuiltinStringType
    )
    func.assert_no_arg()
    # Write
    return NoneCallResult(
        ['titleraw %s clear' % arg_target.value],
        NoneVar(func.compiler), func.compiler
    )

# builder

def acacia_build(compiler):
    compiler.add_type(FStringType)
    return {
        'format': compiler.types[FStringType],
        'tell': BinaryFunction(_tell, compiler),
        'title': BinaryFunction(_title, compiler),
        'TITLE': String(_TITLE, compiler),
        'SUBTITLE': String(_SUBTITLE, compiler),
        'ACTIONBAR': String(_ACTIONBAR, compiler),
        'title_clear': BinaryFunction(_title_clear, compiler)
    }
