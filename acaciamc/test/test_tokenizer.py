"""Unit tests for the tokenizer."""

from typing import List

from acaciamc.test import (
    TestSuite, DiagnosticRequirement, STArgReqSimpleValue, TestFailure
)
from acaciamc.tokenizer import (
    Tokenizer, TokenType as TT, Token, KEYWORDS, INT_LITERAL_BASES
)

class TokenizerTests(TestSuite):
    name = "tokenizer"

    def tokenize(self, *lines: str, mc_version=(1, 20, 10)) -> List[Token]:
        entry = self.owner.reader.add_fake_file('\n'.join(lines))
        tokens = []
        with entry.open() as file:
            tokenizer = Tokenizer(file, entry, self.owner.diag, mc_version)
            with self.owner.diag.capture_errors():
                while True:
                    token = tokenizer.get_next_token()
                    tokens.append(token)
                    if token.type is TT.end_marker:
                        break
        return tokens

    def assert_tokens(self, *lines: str, tokens: List[Token],
                      mc_version=(1, 20, 10),
                      ignore_newlines=True):
        got_tokens = self.tokenize(*lines, mc_version=mc_version)
        if ignore_newlines:
            got_tokens = [tok for tok in got_tokens
                          if tok.type is not TT.new_line]
        if not got_tokens:
            raise TestFailure('No token generated')
        last = got_tokens.pop()
        if last.type is not TT.end_marker:
            raise TestFailure('Last token is not END_MARKER')
        if tokens != got_tokens:
            raise TestFailure('Token streams do not match')

    def test_err_invalid_char(self):
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-char",
            source=((1, 9), (1, 10)),
            args={'char': STArgReqSimpleValue('!')}
        )):
            self.tokenize("spam ham!")
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-char",
            source=((1, 1), (1, 2)),
            args={'char': STArgReqSimpleValue('\t')}
        )):
            self.tokenize("\t")
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-char",
            source=((1, 2), (1, 3)),
            args={'char': STArgReqSimpleValue('\u0660')}
        )):
            self.tokenize("1\u0660")

    def test_err_unmatched_bracket(self):
        with self.assert_diag(DiagnosticRequirement(
            id="unmatched-bracket",
            source=((1, 5), (1, 6)),
            args={'char': STArgReqSimpleValue(']')}
        )):
            self.tokenize("()[]]")

    def test_err_unmatched_bracket_pair(self):
        with self.assert_diag(DiagnosticRequirement(
            id="unmatched-bracket-pair",
            source=((1, 10), (1, 11)),
            args={'open': STArgReqSimpleValue('('),
                  'close': STArgReqSimpleValue(']')}
        )):
            self.tokenize("((){[][]}])")
        with self.assert_diag(DiagnosticRequirement(
            id="unmatched-bracket-pair",
            source=((1, 2), (1, 3)),
            args={'open': STArgReqSimpleValue('{'),
                  'close': STArgReqSimpleValue(']')}
        )):
            self.tokenize("{]")

    def test_err_unclosed_fexpr(self):
        with self.assert_diag(DiagnosticRequirement(
            id="unclosed-fexpr",
            source=((1, 6), (1, 8)),
            args={}
        )):
            self.tokenize('"spam${', 'ham}')
        with self.assert_diag(DiagnosticRequirement(
            id="unclosed-fexpr",
            source=((1, 6), (1, 8)),
            args={}
        )):
            self.tokenize("/foo ${bar", "}")
        with self.assert_diag(DiagnosticRequirement(
            id="unclosed-fexpr",
            source=((1, 7), (1, 9)),
            args={}
        )):
            self.tokenize("/*foo ${", "ham")
        with self.assert_diag(DiagnosticRequirement(
            id="unclosed-fexpr",
            source=((1, 6), (1, 8)),
            args={}
        )):
            self.tokenize('/foo ${"bar${spam}"')

    def test_err_unclosed_long_comment(self):
        with self.assert_diag(DiagnosticRequirement(
            id="unclosed-long-comment",
            source=((1, 5), (1, 7)),
            args={}
        )):
            self.tokenize('foo #* fooooo', 'spam')

    def test_err_unclosed_long_command(self):
        with self.assert_diag(DiagnosticRequirement(
            id="unclosed-long-command",
            source=((1, 1), (1, 3)),
            args={}
        )):
            self.tokenize('/* bar ${spam}', 'ham')

    def test_err_unclosed_bracket(self):
        with self.assert_diag(DiagnosticRequirement(
            id="unclosed-bracket",
            source=((1, 3), (1, 4)),
            args={"char": STArgReqSimpleValue('{')}
        )):
            self.tokenize(
                '(){(',
                '   []',
                ')',
            )

    def test_err_eof_after_continuation(self):
        with self.assert_diag(DiagnosticRequirement(
            id="eof-after-continuation",
            source=((1, 6), (1, 6)),
            args={}
        )):
            self.tokenize('foo \\')

    def test_err_char_after_continuation(self):
        with self.assert_diag(DiagnosticRequirement(
            id="char-after-continuation",
            source=((1, 6), (1, 7)),
            args={}
        )):
            self.tokenize('foo \\a')

    def test_err_interface_path_expected(self):
        with self.assert_diag(DiagnosticRequirement(
            id="interface-path-expected",
            source=((1, 11), (1, 11)),
            args={}
        )):
            self.tokenize('interface ()')
        with self.assert_diag(DiagnosticRequirement(
            id="interface-path-expected",
            source=((1, 10), (1, 10)),
            args={}
        )):
            self.tokenize('interface')

    def test_err_invalid_dedent(self):
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-dedent",
            source=((3, 1), (3, 1)),
            args={}
        )):
            self.tokenize(
                'foo',
                '   bar',
                ' spam',
            )

    def test_err_integer_expected(self):
        for prefix, base in INT_LITERAL_BASES.items():
            with self.assert_diag(DiagnosticRequirement(
                id="integer-expected",
                source=((1, 3), (1, 3)),
                args={'base': STArgReqSimpleValue(base)}
            )):
                self.tokenize(f'0{prefix}')

    def test_err_invalid_number_char(self):
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-number-char",
            source=((1, 3), (1, 4)),
            args={'base': STArgReqSimpleValue(10),
                  'char': STArgReqSimpleValue('a')}
        )):
            self.tokenize("10a")
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-number-char",
            source=((1, 6), (1, 7)),
            args={'base': STArgReqSimpleValue(10),
                  'char': STArgReqSimpleValue('_')}
        )):
            self.tokenize("12.34_")
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-number-char",
            source=((1, 4), (1, 5)),
            args={'base': STArgReqSimpleValue(16),
                  'char': STArgReqSimpleValue('g')}
        )):
            self.tokenize("0xag")
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-number-char",
            source=((1, 3), (1, 4)),
            args={'base': STArgReqSimpleValue(2),
                  'char': STArgReqSimpleValue('2')}
        )):
            self.tokenize("0b222")

    def test_err_unclosed_font(self):
        with self.assert_diag(DiagnosticRequirement(
            id="unclosed-font",
            source=((1, 2), (1, 5)),
            args={}
        )):
            self.tokenize(r'"\#(green"')

    def test_err_invalid_font(self):
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-font",
            source=((1, 13), (1, 17)),
            args={'font': STArgReqSimpleValue('spam')}
        )):
            self.tokenize(r'"\#( bold , spam)"')
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-font",
            source=((1, 7), (1, 10)),
            args={'font': STArgReqSimpleValue('ham')}
        )):
            self.tokenize(r'"\#(  ham )"')
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-font",
            source=((1, 11), (1, 11)),
            args={'font': STArgReqSimpleValue('')}
        )):
            self.tokenize(r'"\#(green, )"')
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-font",
            source=((1, 5), (1, 5)),
            args={'font': STArgReqSimpleValue('')}
        )):
            self.tokenize(r'"\#()"')

    def test_err_incomplete_unicode_escape(self):
        with self.assert_diag(DiagnosticRequirement(
            id="incomplete-unicode-escape",
            source=((1, 2), (1, 4)),
            args={'char': STArgReqSimpleValue('x')}
        )):
            self.tokenize(r'"\x"')
        with self.assert_diag(DiagnosticRequirement(
            id="incomplete-unicode-escape",
            source=((1, 2), (1, 4)),
            args={'char': STArgReqSimpleValue('u')}
        )):
            self.tokenize(r'"\u777g"')

    def test_err_invalid_unicode_code_point(self):
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-unicode-code-point",
            source=((1, 4), (1, 12)),
            args={'code': STArgReqSimpleValue('001100Af')}
        )):
            self.tokenize(r'"\U001100Af"')

    def test_err_incomplete_escape(self):
        with self.assert_diag(DiagnosticRequirement(
            id="incomplete-escape",
            source=((1, 6), (1, 7)),
            args={}
        )):
            self.tokenize(r'"xx\"' + '\\')

    def test_err_invalid_escape(self):
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-escape",
            source=((1, 2), (1, 4)),
            args={"character": STArgReqSimpleValue("X")}
        )):
            self.tokenize(r'"\X55"')
        with self.assert_diag(DiagnosticRequirement(
            id="invalid-escape",
            source=((1, 3), (1, 5)),
            args={"character": STArgReqSimpleValue(" ")}
        )):
            self.tokenize(r'"x\  "')

    def test_unclosed_quote(self):
        with self.assert_diag(DiagnosticRequirement(
            id="unclosed-quote",
            source=((1, 1), (1, 2)),
            args={}
        )):
            self.tokenize('"spam')
        with self.assert_diag(DiagnosticRequirement(
            id="unclosed-quote",
            source=((1, 8), (1, 9)),
            args={}
        )):
            self.tokenize('"spam${"spam')

    def test_warn_new_font(self):
        with self.assert_diag(DiagnosticRequirement(
            id="new-font",
            source=((1, 12), (1, 28)),
            args={'font': STArgReqSimpleValue('material_diamond')}
        )):
            self.tokenize(r'"\#(green, material_diamond)"',
                          mc_version=(1, 19, 70))

    def test_integer(self):
        self.assert_tokens(
            '1230987 0b0001100 0o77665 0XfAc2 00222 0',
            tokens=[
                Token(TT.integer, (1, 1), (1, 8), 1230987),
                Token(TT.integer, (1, 9), (1, 18), 0b0001100),
                Token(TT.integer, (1, 19), (1, 26), 0o77665),
                Token(TT.integer, (1, 27), (1, 33), 0xfac2),
                Token(TT.integer, (1, 34), (1, 39), 222),
                Token(TT.integer, (1, 40), (1, 41), 0),
            ]
        )

    def test_float(self):
        self.assert_tokens(
            '12.234 0.1 0.0003 10000.0',
            tokens=[
                Token(TT.float, (1, 1), (1, 7), value=12.234),
                Token(TT.float, (1, 8), (1, 11), value=0.1),
                Token(TT.float, (1, 12), (1, 18), value=0.0003),
                Token(TT.float, (1, 19), (1, 26), value=10000.0),
            ]
        )
        # These look like floats...
        self.assert_tokens(
            '.2 0x12.3 1.x',
            tokens=[
                Token(TT.point, (1, 1), (1, 2)),
                Token(TT.integer, (1, 2), (1, 3), value=2),
                Token(TT.integer, (1, 4), (1, 8), value=0x12),
                Token(TT.point, (1, 8), (1, 9)),
                Token(TT.integer, (1, 9), (1, 10), value=3),
                Token(TT.integer, (1, 11), (1, 12), value=1),
                Token(TT.point, (1, 12), (1, 13)),
                Token(TT.identifier, (1, 13), (1, 14), value='x'),
            ]
        )

    def test_string(self):
        self.assert_tokens(
            r'"foo #+$" spam "foo${bar}" "\"ham\""',
            tokens=[
                Token(TT.string_begin, (1, 1), (1, 2)),
                Token(TT.text_body, (1, 2), (1, 9), value='foo #+$'),
                Token(TT.string_end, (1, 9), (1, 10)),
                Token(TT.identifier, (1, 11), (1, 15), value='spam'),
                Token(TT.string_begin, (1, 16), (1, 17)),
                Token(TT.text_body, (1, 17), (1, 20), value='foo'),
                Token(TT.dollar_lbrace, (1, 20), (1, 22)),
                Token(TT.identifier, (1, 22), (1, 25), value='bar'),
                Token(TT.rbrace, (1, 25), (1, 26)),
                Token(TT.string_end, (1, 26), (1, 27)),
                Token(TT.string_begin, (1, 28), (1, 29)),
                Token(TT.text_body, (1, 29), (1, 36), value='"ham"'),
                Token(TT.string_end, (1, 36), (1, 37)),
            ]
        )

    def test_command(self):
        self.assert_tokens(
            '/foo ### spam!',
            r'/ \"ham',
            '/*',
            '# foo',
            '   /**',
            '**/',
            '/${1000} works',
            tokens=[
                Token(TT.command_begin, (1, 1), (1, 2)),
                Token(TT.text_body, (1, 2), (1, 15), value='foo ### spam!'),
                Token(TT.command_end, (1, 15), (1, 15)),
                Token(TT.command_begin, (2, 1), (2, 2)),
                Token(TT.text_body, (2, 2), (2, 8), value=' "ham'),
                Token(TT.command_end, (2, 8), (2, 8)),
                Token(TT.command_begin, (3, 1), (3, 3)),
                Token(TT.text_body, (3, 3), (6, 2), value=' # foo    /** *'),
                Token(TT.command_end, (6, 2), (6, 4)),
                Token(TT.command_begin, (7, 1), (7, 2)),
                Token(TT.dollar_lbrace, (7, 2), (7, 4)),
                Token(TT.integer, (7, 4), (7, 8), value=1000),
                Token(TT.rbrace, (7, 8), (7, 9)),
                Token(TT.text_body, (7, 9), (7, 15), value=' works'),
                Token(TT.command_end, (7, 15), (7, 15)),
            ]
        )

    def test_escapes(self):
        self.assert_tokens(
            r'"\#a\#(green, bold)\x77\u0066\U00000055\#(material_quartz)'
            r'\n\\\$"',
            tokens=[
                Token(TT.string_begin, (1, 1), (1, 2)),
                Token(TT.text_body, (1, 2), (1, 65),
                      value='\xa7a\xa7a\xa7lwfU\xa7h\n\\$'),
                Token(TT.string_end, (1, 65), (1, 66)),
            ]
        )

    def test_fexpr(self):
        self.assert_tokens(
            '"a ${c} b ${1}${2} ${{3, "d ${"e"}"}()}"',
            tokens=[
                Token(TT.string_begin, (1, 1), (1, 2)),
                Token(TT.text_body, (1, 2), (1, 4), value='a '),
                Token(TT.dollar_lbrace, (1, 4), (1, 6)),
                Token(TT.identifier, (1, 6), (1, 7), value='c'),
                Token(TT.rbrace, (1, 7), (1, 8)),
                Token(TT.text_body, (1, 8), (1, 11), value=' b '),
                Token(TT.dollar_lbrace, (1, 11), (1, 13)),
                Token(TT.integer, (1, 13), (1, 14), value=1),
                Token(TT.rbrace, (1, 14), (1, 15)),
                Token(TT.dollar_lbrace, (1, 15), (1, 17)),
                Token(TT.integer, (1, 17), (1, 18), value=2),
                Token(TT.rbrace, (1, 18), (1, 19)),
                Token(TT.text_body, (1, 19), (1, 20), value=' '),
                Token(TT.dollar_lbrace, (1, 20), (1, 22)),
                Token(TT.lbrace, (1, 22), (1, 23)),
                Token(TT.integer, (1, 23), (1, 24), value=3),
                Token(TT.comma, (1, 24), (1, 25)),
                Token(TT.string_begin, (1, 26), (1, 27)),
                Token(TT.text_body, (1, 27), (1, 29), value='d '),
                Token(TT.dollar_lbrace, (1, 29), (1, 31)),
                Token(TT.string_begin, (1, 31), (1, 32)),
                Token(TT.text_body, (1, 32), (1, 33), value='e'),
                Token(TT.string_end, (1, 33), (1, 34)),
                Token(TT.rbrace, (1, 34), (1, 35)),
                Token(TT.string_end, (1, 35), (1, 36)),
                Token(TT.rbrace, (1, 36), (1, 37)),
                Token(TT.lparen, (1, 37), (1, 38)),
                Token(TT.rparen, (1, 38), (1, 39)),
                Token(TT.rbrace, (1, 39), (1, 40)),
                Token(TT.string_end, (1, 40), (1, 41)),
            ]
        )

    def test_indent(self):
        self.assert_tokens(
            'foo',
            '   bar',
            '   spam \\',
            'eggs',
            '  # ham',
            '       wood',
            'axe',
            '    \\',
            '',
            tokens=[
                Token(TT.identifier, (1, 1), (1, 4), value='foo'),
                Token(TT.new_line, (1, 4), (1, 5)),
                Token(TT.indent, (2, 1), (2, 4)),
                Token(TT.identifier, (2, 4), (2, 7), value='bar'),
                Token(TT.new_line, (2, 7), (2, 8)),
                Token(TT.identifier, (3, 4), (3, 8), value='spam'),
                Token(TT.identifier, (4, 1), (4, 5), value='eggs'),
                Token(TT.new_line, (4, 5), (4, 6)),
                Token(TT.indent, (6, 1), (6, 8)),
                Token(TT.identifier, (6, 8), (6, 12), value='wood'),
                Token(TT.new_line, (6, 12), (6, 13)),
                Token(TT.dedent, (7, 1), (7, 1)),
                Token(TT.dedent, (7, 1), (7, 1)),
                Token(TT.identifier, (7, 1), (7, 4), value='axe'),
                Token(TT.new_line, (7, 4), (7, 5)),
                Token(TT.indent, (8, 1), (8, 5)),
                Token(TT.dedent, (9, 1), (9, 1)),
            ],
            ignore_newlines=False
        )

    def test_comment(self):
        self.assert_tokens(
            '# aaa',
            '1 #* bbb *# 2',
            '  # ok',
            '#*',
            '  #*  ok',
            '*#',
            tokens=[
                Token(TT.integer, (2, 1), (2, 2), value=1),
                Token(TT.integer, (2, 13), (2, 14), value=2)
            ]
        )

    def test_newline(self):
        self.assert_tokens(
            '1 2',
            '3',
            '',
            '#* *# 4',
            '5 \\',
            '6',
            tokens=[
                Token(TT.integer, (1, 1), (1, 2), value=1),
                Token(TT.integer, (1, 3), (1, 4), value=2),
                Token(TT.new_line, (1, 4), (1, 5)),
                Token(TT.integer, (2, 1), (2, 2), value=3),
                Token(TT.new_line, (2, 2), (2, 3)),
                Token(TT.integer, (4, 7), (4, 8), value=4),
                Token(TT.new_line, (4, 8), (4, 9)),
                Token(TT.integer, (5, 1), (5, 2), value=5),
                Token(TT.integer, (6, 1), (6, 2), value=6),
                Token(TT.new_line, (6, 2), (6, 2)),
            ],
            ignore_newlines=False
        )

    def test_line_continuation(self):
        self.assert_tokens(
            '1 \\',
            '  2',
            '# 3 \\',
            '4 \\',
            '\\',
            '5',
            '   \\',
            '6',
            tokens=[
                Token(TT.integer, (1, 1), (1, 2), value=1),
                Token(TT.integer, (2, 3), (2, 4), value=2),
                Token(TT.new_line, (2, 4), (2, 5)),
                Token(TT.integer, (4, 1), (4, 2), value=4),
                Token(TT.integer, (6, 1), (6, 2), value=5),
                Token(TT.new_line, (6, 2), (6, 3)),
                Token(TT.indent, (7, 1), (7, 4)),
                Token(TT.integer, (8, 1), (8, 2), value=6),
                Token(TT.new_line, (8, 2), (8, 2)),
                Token(TT.dedent, (8, 2), (8, 2)),
            ],
            ignore_newlines=False
        )

    def test_bracket_continuation(self):
        self.assert_tokens(
            '(',
            '    {',
            '        foo',
            '    }',
            '    1',
            '        # foo',
            '            2',
            ')',
            '[',
            '    bar',
            ']',
            tokens=[
                Token(TT.lparen, (1, 1), (1, 2)),
                Token(TT.lbrace, (2, 5), (2, 6)),
                Token(TT.identifier, (3, 9), (3, 12), value='foo'),
                Token(TT.rbrace, (4, 5), (4, 6)),
                Token(TT.integer, (5, 5), (5, 6), value=1),
                Token(TT.integer, (7, 13), (7, 14), value=2),
                Token(TT.rparen, (8, 1), (8, 2)),
                Token(TT.new_line, (8, 2), (8, 3)),
                Token(TT.lbracket, (9, 1), (9, 2)),
                Token(TT.identifier, (10, 5), (10, 8), value='bar'),
                Token(TT.rbracket, (11, 1), (11, 2)),
                Token(TT.new_line, (11, 2), (11, 2)),
            ],
            ignore_newlines=False
        )

    def test_bracket(self):
        self.assert_tokens(
            '(([]{[]})())[]',
            tokens=[
                Token(TT.lparen, (1, 1), (1, 2)),
                Token(TT.lparen, (1, 2), (1, 3)),
                Token(TT.lbracket, (1, 3), (1, 4)),
                Token(TT.rbracket, (1, 4), (1, 5)),
                Token(TT.lbrace, (1, 5), (1, 6)),
                Token(TT.lbracket, (1, 6), (1, 7)),
                Token(TT.rbracket, (1, 7), (1, 8)),
                Token(TT.rbrace, (1, 8), (1, 9)),
                Token(TT.rparen, (1, 9), (1, 10)),
                Token(TT.lparen, (1, 10), (1, 11)),
                Token(TT.rparen, (1, 11), (1, 12)),
                Token(TT.rparen, (1, 12), (1, 13)),
                Token(TT.lbracket, (1, 13), (1, 14)),
                Token(TT.rbracket, (1, 14), (1, 15)),
            ]
        )

    def test_op(self):
        self.assert_tokens(
            ':,+-*/%><.=@&',
            tokens=[
                Token(TT.colon, (1, 1), (1, 2)),
                Token(TT.comma, (1, 2), (1, 3)),
                Token(TT.plus, (1, 3), (1, 4)),
                Token(TT.minus, (1, 4), (1, 5)),
                Token(TT.star, (1, 5), (1, 6)),
                Token(TT.slash, (1, 6), (1, 7)),
                Token(TT.mod, (1, 7), (1, 8)),
                Token(TT.greater, (1, 8), (1, 9)),
                Token(TT.less, (1, 9), (1, 10)),
                Token(TT.point, (1, 10), (1, 11)),
                Token(TT.equal, (1, 11), (1, 12)),
                Token(TT.at, (1, 12), (1, 13)),
                Token(TT.ampersand, (1, 13), (1, 14)),
            ]
        )
        self.assert_tokens(
            '++=-==*===/=!=>=<=->:=',
            tokens=[
                Token(TT.plus, (1, 1), (1, 2)),
                Token(TT.plus_equal, (1, 2), (1, 4)),
                Token(TT.minus_equal, (1, 4), (1, 6)),
                Token(TT.equal, (1, 6), (1, 7)),
                Token(TT.times_equal, (1, 7), (1, 9)),
                Token(TT.equal_to, (1, 9), (1, 11)),
                Token(TT.divide_equal, (1, 11), (1, 13)),
                Token(TT.unequal_to, (1, 13), (1, 15)),
                Token(TT.greater_equal, (1, 15), (1, 17)),
                Token(TT.less_equal, (1, 17), (1, 19)),
                Token(TT.arrow, (1, 19), (1, 21)),
                Token(TT.walrus, (1, 21), (1, 23)),
            ]
        )

    def test_interface_path(self):
        self.assert_tokens(
            'interface spam/ham/_1-2',
            'interface aaa11-bb_1.2()',
            'interface "xxx${1}"',
            'interface if',
            tokens=[
                Token(TT.interface, (1, 1), (1, 10)),
                Token(TT.interface_path, (1, 11), (1, 24),
                      value='spam/ham/_1-2'),
                Token(TT.interface, (2, 1), (2, 10)),
                Token(TT.interface_path, (2, 11), (2, 23),
                      value='aaa11-bb_1.2'),
                Token(TT.lparen, (2, 23), (2, 24)),
                Token(TT.rparen, (2, 24), (2, 25)),
                Token(TT.interface, (3, 1), (3, 10)),
                Token(TT.string_begin, (3, 11), (3, 12)),
                Token(TT.text_body, (3, 12), (3, 15), value='xxx'),
                Token(TT.dollar_lbrace, (3, 15), (3, 17)),
                Token(TT.integer, (3, 17), (3, 18), value=1),
                Token(TT.rbrace, (3, 18), (3, 19)),
                Token(TT.string_end, (3, 19), (3, 20)),
                Token(TT.interface, (4, 1), (4, 10)),
                Token(TT.interface_path, (4, 11), (4, 13), value='if'),
            ]
        )

    def test_identifier(self):
        self.assert_tokens(
            'foo _spam1 ___xx_ _0 fran\xe7ais \u4f60\u597d1 if_3 _else',
            tokens=[
                Token(TT.identifier, (1, 1), (1, 4), value='foo'),
                Token(TT.identifier, (1, 5), (1, 11), value='_spam1'),
                Token(TT.identifier, (1, 12), (1, 18), value='___xx_'),
                Token(TT.identifier, (1, 19), (1, 21), value='_0'),
                Token(TT.identifier, (1, 22), (1, 30), value='fran\xe7ais'),
                Token(TT.identifier, (1, 31), (1, 34), value='\u4f60\u597d1'),
                Token(TT.identifier, (1, 35), (1, 39), value='if_3'),
                Token(TT.identifier, (1, 40), (1, 45), value='_else'),
            ]
        )

    def test_keywords(self):
        # Pick some random keywords to check if KEYWORDS is correctly
        # generated:
        self.assert_true(
            'True' in KEYWORDS and 'interface' in KEYWORDS
                and 'from' in KEYWORDS,
            'KEYWORDS is not correctly generated'
        )
        my_keywords = KEYWORDS.copy()
        # Avoid interface-path-expected
        my_keywords.pop('interface')
        self.assert_tokens(
            *my_keywords,
            tokens=[
                Token(tok, (i, 1), (i, len(kw) + 1))
                for i, (kw, tok) in enumerate(my_keywords.items(), start=1)
            ]
        )

def token_to_test_repr(token: Token) -> str:
    """
    Return a string representation used for writing expected output of
    the tokenizer.
    """
    if token.value is None:
        value_str = ''
    else:
        value_str = f', value={token.value!r}'
    return (f'Token(TT.{token.type.name}, '
            f'{token.pos1}, {token.pos2}{value_str})')

def tokenize_test_repr(*lines: str, mc_version=(1, 20, 10)):
    """
    Used as a script.
    Tokenize `lines` and display tokens using `token_to_test_repr`.
    """
    from acaciamc.reader import Reader
    from acaciamc.diagnostic import DiagnosticsManager

    reader = Reader()
    diag = DiagnosticsManager(reader)
    entry = reader.add_fake_file('\n'.join(lines))
    with entry.open() as file:
        tokenizer = Tokenizer(file, entry, diag, mc_version)
        with diag.capture_errors():
            while True:
                token = tokenizer.get_next_token()
                print(token_to_test_repr(token) + ',')
                if token.type is TT.end_marker:
                    break
