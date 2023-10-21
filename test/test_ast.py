# Visualize the Abstract Grammar Tree of code

# Add `acaciamc` directory to path
import os
import sys
sys.path.append(os.path.realpath(
    os.path.join(__file__, os.pardir, os.pardir)
))

import io
from types import MethodType

from acaciamc.tokenizer import Tokenizer, TokenType
from acaciamc.parser import Parser
from acaciamc.error import *
from acaciamc.ast import *

class ASTVisualizer(ASTVisitor):
    def __init__(self, node: AST):
        self.node = node
        super().__init__()

    @staticmethod
    def get_fields(node: AST):
        # get the names of fields of a node
        return filter(
            lambda name:
                not name.startswith('_')
                and name != 'lineno'
                and name != 'col',
            dir(node)
        )

    def general_visit(self, node: AST, indent = 0):
        # indent:int the indent spaces to add (for recursion)
        res = '%s(\n' % node.__class__.__name__
        for field in self.get_fields(node):
            # get sub value
            value = getattr(node, field)
            if isinstance(value, AST):
                substr = self.visit(value, indent=(indent + 2))
            elif isinstance(value, list):
                substr = '[\n'
                for element in value:
                    if isinstance(element, AST):
                        subsub = self.visit(element, indent=(indent + 4))
                    else: subsub = str(element)
                    substr += '%s%s\n' % (
                        ' ' * (indent + 4),
                        subsub
                    )
                substr += '%s]' % (' ' * (indent + 2))
            elif isinstance(value, dict):
                substr = '{\n'
                for k, v in value.items():
                    if isinstance(v, AST):
                        subsub = self.visit(v, indent=(indent + 4))
                    else:
                        subsub = str(v)
                    substr += '%s%s: %s\n' % (
                        ' ' * (indent + 4),
                        k, subsub
                    )
                substr += '%s}' % (' ' * (indent + 2))
            elif not isinstance(value, MethodType):
                substr = str(value)
            else:
                continue
            # connect string
            res += '%s%s = %s\n' % (
                ' ' * (indent + 2),
                field,
                substr
            )
        res += '%s)' % (' ' * indent)
        return res

    def get_string(self):
        return self.visit(self.node)

def test_tokenize(src: str):
    print('===TOKENIZER===')
    tk = Tokenizer(io.StringIO(src))
    while True:
        token = tk.get_next_token()
        print(token)
        if token.type is TokenType.end_marker:
            break

def test_parser(src: str):
    print('===PARSER===')
    parser = Parser(Tokenizer(io.StringIO(src)))
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

score_test = '''
x = |"@p": "score"| + 10
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
        result X@self.get() + 1
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

array_map_test = '''
{1, 2, 3}
{1, 2,}
{1: 2, 3: 4}
{{1: 2,}, 3, {4}}
{:}
{}
'''

try:
    test(multiline_test)
except Error as err:
    err.location.file = "<testsrc>"
    print("Error:", err)
