# Visualize the Abstract Grammar Tree of code

# Add `acaciamc` directory to path
import os
import sys

sys.path.append(os.path.realpath(
    os.path.join(__file__, os.pardir, os.pardir)
))

import io
from types import MethodType
from typing import List, Dict, Type as PyType

from acaciamc.tokenizer import Tokenizer, TokenType
from acaciamc.parser import Parser
from acaciamc.error import *
from acaciamc.ast import AST

MC_VERSION = (1, 19, 80)


class ASTVisualizer:
    _fields_cache: Dict[PyType[AST], List[str]] = {}

    def __init__(self, node: AST, indent=2):
        self.node = node
        self.indent = indent
        super().__init__()

    @classmethod
    def get_fields(cls, node: AST) -> List[str]:
        """Get the names of fields of a node."""
        tp = type(node)
        if tp not in cls._fields_cache:
            cls._fields_cache[tp] = [
                name for name in dir(node)
                if (
                        not name.startswith('_')
                        and name != 'lineno'
                        and name != 'col'
                        and name != 'show_debug'
                )
            ]
        return cls._fields_cache[tp]

    def _convert(self, value, indent: int = 0) -> str:
        res: List[str] = []
        indent_next = indent + self.indent
        if isinstance(value, AST):
            res.append(
                '@%d:%d %s(\n' % (
                    value.lineno, value.col,
                    value.__class__.__name__
                )
            )
            for field in self.get_fields(value):
                fvalue = getattr(value, field)
                if isinstance(fvalue, MethodType):
                    continue
                res.append('%s%s = %s\n' % (
                    ' ' * indent_next, field,
                    self._convert(fvalue, indent=indent_next)
                ))
            res.append('%s)' % (' ' * indent))
        elif isinstance(value, list):
            res.append('[\n')
            for element in value:
                sub = self._convert(element, indent=(indent + self.indent))
                res.append('%s%s\n' % (' ' * indent_next, sub))
            res.append('%s]' % (' ' * indent))
        elif isinstance(value, dict):
            res.append('{\n')
            for k, v in value.items():
                sub = self._convert(v, indent=(indent + self.indent))
                res.append('%s%r: %s\n' % (' ' * indent_next, k, sub))
            res.append('%s}' % (' ' * indent))
        else:
            res.append(repr(value))
        return "".join(res)

    def get_string(self) -> str:
        return self._convert(self.node)


def test_tokenize(src: str):
    print('===TOKENIZER===')
    tk = Tokenizer(io.StringIO(src), MC_VERSION)
    while True:
        token = tk.get_next_token()
        print(repr(token))
        if token.type is TokenType.end_marker:
            break


def test_parser(src: str):
    print('===PARSER===')
    parser = Parser(Tokenizer(io.StringIO(src), MC_VERSION))
    visualizer = ASTVisualizer(parser.module())
    print(visualizer.get_string())


def test(src: str):
    test_tokenize(src)
    test_parser(src)


definition_test = '''
interface x:
    pass
def x(a: int, b=True) -> a:
    pass
'''

if_test = '''if a:
    # a comment

    #*pass*# pass
    if a + 1:
        1
elif a:  # a comment
    pass'''

attr_test = '''
aaa
a.b(1, a+2, c=3,)
b.c().d
'''

operator_test = '''
a > b > c + 1 <= 4 and not 11 > 6 or b
'''

assign_test = '''
"money":"@p" = 1
b -> "money":"@p"
a.b.c *= 5 % b
'''

backslash_test = '''
a = \\
    3
    \\
  # a comment

x = \\
  10 \\
    + 20

'''

entity_test = '''
entity X:
    x: int
    inline def get() -> int:
        result self.x

entity Y extends X:
    def get():
        result upcast(self, X).get() + 1
'''

decimal_test = '''
1.2  # 1.2
02.foo  # (2).foo
0x10.f  # (16).f (float does not support hex form)
'''

multiline_test = '''
 #* mul *# if x:
    #* xx
    g \\
        y
        *# (y
      # xxx
    + z)
        /*sss ${1}
  sss*/ 5'''

list_map_test = '''
{1, 2, 3}
{1, 2,}
{1: 2, 3: 4}
{{1: 2,}, 3, {4}}
{:}
{}
'''

command_test = '''
/sss
/*  a \${ */
/s${xxx}ss
{}
/*${1
}
f
*/
/*xxx${aaa *
    some_expr +
    # comment
    1 \\
        + {"embedded"}
}*/
/*${"xx\${xx${{xxx}[0] + "qqq${1}ppp"}ggg"}*/
'''

new_test = '''
entity X:
    new(x: int):
        new(xxx)
entity Y extends X:
    inline new(&y: bool):
        X.new(yyy)
'''

try:
    test(new_test)
except Error as err:
    err.location.file = "<testsrc>"
    print("Error:", err)
