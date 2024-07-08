"""Unit tests for Acacia's parser"""

from typing import Dict, Any, Tuple, Optional
from functools import partialmethod
from collections import OrderedDict

import acaciamc.ast as ast
from acaciamc.test import (
    TestSuite, DiagnosticRequirement, TestFailure,
    STArgRequirement, STArgReqSimpleValue
)
from acaciamc.tokenizer import Tokenizer, TokenType
from acaciamc.parser import Parser, STToken
from acaciamc.utils.str_template import STArgument

EXPR_SNIPPETS: Tuple[Tuple[str, Dict[str, Any]], ...] = (
    ("None", {"@type": ast.NoneLiteral, "begin": (1, 1), "end": (1, 5)}),
    ("42", {"@type": ast.IntLiteral, "value": 42,
            "begin": (1, 1), "end": (1, 3)}),
    ("True", {"@type": ast.BoolLiteral, "value": True,
              "begin": (1, 1), "end": (1, 5)}),
    ("2.2", {"@type": ast.FloatLiteral, "value": 2.2,
             "begin": (1, 1), "end": (1, 4)}),
    ('"foo"', {"@type": ast.StrLiteral, "begin": (1, 1), "end": (1, 6),
               "content": {"@type": ast.FormattedStr, "content": ["foo"]}}),
    ('"ham${wood}"', {
        "@type": ast.StrLiteral, "begin": (1, 1), "end": (1, 13),
        "content": {
            "@type": ast.FormattedStr, "content": [
                "ham", {"@type": ast.Identifier, "name": "wood",
                        "begin": (1, 7), "end": (1, 11)}
            ]
        }
    }),
    ("self", {"@type": ast.Self, "begin": (1, 1), "end": (1, 5)}),
    ("+x", {"@type": ast.UnaryOp, "begin": (1, 1), "end": (1, 3),
            "operator": {"@type": ast.UnaryAdd,
                         "begin": (1, 1), "end": (1, 2)},
            "operand": {"@type": ast.Identifier, "name": "x",
                        "begin": (1, 2), "end": (1, 3)}}),
    ("x-y", {"@type": ast.BinOp, "begin": (1, 1), "end": (1, 4),
             "operator": {"@type": ast.Sub,
                          "begin": (1, 2), "end": (1, 3)},
             "left": {"@type": ast.Identifier, "name": "x",
                      "begin": (1, 1), "end": (1, 2)},
             "right": {"@type": ast.Identifier, "name": "y",
                       "begin": (1, 3), "end": (1, 4)}}),
    ("x*y/z", {
        "@type": ast.BinOp, "begin": (1, 1), "end": (1, 6),
        "operator": {"@type": ast.Div, "begin": (1, 4), "end": (1, 5)},
        "right": {"@type": ast.Identifier, "name": "z",
                  "begin": (1, 5), "end": (1, 6)},
        "left": {
            "@type": ast.BinOp, "begin": (1, 1), "end": (1, 4),
            "operator": {"@type": ast.Mul, "begin": (1, 2), "end": (1, 3)},
            "left": {"@type": ast.Identifier, "name": "x",
                     "begin": (1, 1), "end": (1, 2)},
            "right": {"@type": ast.Identifier, "name": "y",
                      "begin": (1, 3), "end": (1, 4)},
        }
    }),
    ("x-y%z", {
        "@type": ast.BinOp, "begin": (1, 1), "end": (1, 6),
        "operator": {"@type": ast.Sub, "begin": (1, 2), "end": (1, 3)},
        "left": {"@type": ast.Identifier, "name": "x",
                 "begin": (1, 1), "end": (1, 2)},
        "right": {
            "@type": ast.BinOp, "begin": (1, 3), "end": (1, 6),
            "operator": {"@type": ast.Mod, "begin": (1, 4), "end": (1, 5)},
            "left": {"@type": ast.Identifier, "name": "y",
                     "begin": (1, 3), "end": (1, 4)},
            "right": {"@type": ast.Identifier, "name": "z",
                      "begin": (1, 5), "end": (1, 6)},
        }
    }),
    ("f()", {"@type": ast.Call, "begin": (1, 1), "end": (1, 4),
             "func": {"@type": ast.Identifier, "name": "f",
                      "begin": (1, 1), "end": (1, 2)},
             "table": {"@type": ast.CallTable, "args": [], "keywords": {}}}),
    ("f(2, x=1)", {
        "@type": ast.Call, "begin": (1, 1), "end": (1, 10),
        "func": {"@type": ast.Identifier, "name": "f",
                 "begin": (1, 1), "end": (1, 2)},
        "table": {
            "@type": ast.CallTable,
            "args": [{"@type": ast.IntLiteral, "value": 2,
                      "begin": (1, 3), "end": (1, 4)}],
            "keywords": {"x": {
                "@type": ast.IntLiteral, "value": 1,
                "begin": (1, 8), "end": (1, 9)
            }}
        }
    }),
    ("x.y.z", {
        "@type": ast.Attribute, "begin": (1, 1), "end": (1, 6), "attr": "z",
        "object": {
            "@type": ast.Attribute, "begin": (1, 1), "end": (1, 4),
            "attr": "y", "object": {
                "@type": ast.Identifier, "begin": (1, 1), "end": (1, 2),
                "name": "x"
            }
        }
    }),
    ("x[y,z]", {
        "@type": ast.Subscript, "begin": (1, 1), "end": (1, 7),
        "object": {"@type": ast.Identifier, "begin": (1, 1), "end": (1, 2),
                   "name": "x"},
        "subscripts": [
            {"@type": ast.Identifier, "begin": (1, 3), "end": (1, 4),
             "name": "y"},
            {"@type": ast.Identifier, "begin": (1, 5), "end": (1, 6),
             "name": "z"},
        ]
    }),
    ("x<y<=z", {
        "@type": ast.CompareOp, "begin": (1, 1), "end": (1, 7),
        "left": {"@type": ast.Identifier, "begin": (1, 1), "end": (1, 2),
                 "name": "x"},
        "operators": [
            {"@type": ast.Less, "begin": (1, 2), "end": (1, 3)},
            {"@type": ast.LessEqual, "begin": (1, 4), "end": (1, 6)}
        ],
        "operands": [
            {"@type": ast.Identifier, "begin": (1, 3), "end": (1, 4),
             "name": "y"},
            {"@type": ast.Identifier, "begin": (1, 6), "end": (1, 7),
             "name": "z"}
        ]
    }),
    ("a and b or c", {
        "@type": ast.BoolOp, "begin": (1, 1), "end": (1, 13),
        "operator": {"@type": ast.Or},
        "operands": [
            {
                "@type": ast.BoolOp, "begin": (1, 1), "end": (1, 8),
                "operator": {"@type": ast.And},
                "operands": [
                    {"@type": ast.Identifier, "begin": (1, 1), "end": (1, 2),
                     "name": "a"},
                    {"@type": ast.Identifier, "begin": (1, 7), "end": (1, 8),
                     "name": "b"}
                ]
            },
            {"@type": ast.Identifier, "begin": (1, 12), "end": (1, 13),
             "name": "c"}
        ]
    }),
    ("{}",
     {"@type": ast.ListDef, "begin": (1, 1), "end": (1, 3), "items": []}),
    ("{:}", {"@type": ast.MapDef, "begin": (1, 1), "end": (1, 4),
             "keys": [], "values": []}),
    ("{1,2,3}", {
        "@type": ast.ListDef, "begin": (1, 1), "end": (1, 8),
        "items": [
            {"@type": ast.IntLiteral, "value": 1,
             "begin": (1, 2), "end": (1, 3)},
            {"@type": ast.IntLiteral, "value": 2,
             "begin": (1, 4), "end": (1, 5)},
            {"@type": ast.IntLiteral, "value": 3,
             "begin": (1, 6), "end": (1, 7)},
        ]
    }),
    ("{1:2,2:3,3:4}", {
        "@type": ast.MapDef, "begin": (1, 1), "end": (1, 14),
        "keys": [
            {"@type": ast.IntLiteral, "value": 1,
             "begin": (1, 2), "end": (1, 3)},
            {"@type": ast.IntLiteral, "value": 2,
             "begin": (1, 6), "end": (1, 7)},
            {"@type": ast.IntLiteral, "value": 3,
             "begin": (1, 10), "end": (1, 11)},
        ],
        "values": [
            {"@type": ast.IntLiteral, "value": 2,
             "begin": (1, 4), "end": (1, 5)},
            {"@type": ast.IntLiteral, "value": 3,
             "begin": (1, 8), "end": (1, 9)},
            {"@type": ast.IntLiteral, "value": 4,
             "begin": (1, 12), "end": (1, 13)},
        ]
    }),
)

STMT_SNIPPETS: Tuple[Tuple[str, Dict[str, Any]], ...] = (
    ("foo", {"@type": ast.ExprStatement,
             "begin": (1, 1), "end": (1, 4),
             "value": {"@type": ast.Identifier, "name": "foo"}}),
    ("pass", {"@type": ast.Pass, "begin": (1, 1), "end": (1, 5)}),
    ("if x:\n pass", {
        "@type": ast.If, "begin": (1, 1), "end": (2, 6),
        "condition": {
            "@type": ast.Identifier, "begin": (1, 4), "end": (1, 5),
            "name": "x"
        },
        "body": [{"@type": ast.Pass, "begin": (2, 2), "end": (2, 6)}],
        "else_body": []
    }),
    ("if x:\n pass\nelif y:\n pass\nelse:\n pass\n", {
        "@type": ast.If, "begin": (1, 1), "end": (6, 6),
        "condition": {
            "@type": ast.Identifier, "begin": (1, 4), "end": (1, 5),
            "name": "x"
        },
        "body": [{"@type": ast.Pass, "begin": (2, 2), "end": (2, 6)}],
        "else_body": [{
            "@type": ast.If, "begin": (3, 1), "end": (6, 6),
            "condition": {
                "@type": ast.Identifier, "begin": (3, 6), "end": (3, 7),
                "name": "y"
            },
            "body": [{"@type": ast.Pass, "begin": (4, 2), "end": (4, 6)}],
            "else_body": [{"@type": ast.Pass, "begin": (6, 2), "end": (6, 6)}]
        }]
    }),
    ("while x:\n pass", {
        "@type": ast.While, "begin": (1, 1), "end": (2, 6),
        "condition": {
            "@type": ast.Identifier, "begin": (1, 7), "end": (1, 8),
            "name": "x"
        },
        "body": [{"@type": ast.Pass, "begin": (2, 2), "end": (2, 6)}]
    }),
    ("def f():\n pass", {
        "@type": ast.FuncDef, "begin": (1, 1), "end": (2, 6),
        "name": {
            "@type": ast.IdentifierDef, "name": "f",
            "begin": (1, 5), "end": (1, 6)
        },
        "data": {
            "@type": ast.NormalFuncData,
            "arg_table": {
                "@type": ast.ArgumentTable,
                "params": OrderedDict(),
            },
            "returns": None,
            "body": [{"@type": ast.Pass, "begin": (2, 2), "end": (2, 6)}]
        }
    }),
    ("inline def f(x, y: int, const z=10) -> int:\n pass", {
        "@type": ast.FuncDef, "begin": (1, 1), "end": (2, 6),
        "name": {
            "@type": ast.IdentifierDef, "name": "f",
            "begin": (1, 12), "end": (1, 13)
        },
        "data": {
            "@type": ast.InlineFuncData,
            "arg_table": {
                "@type": ast.ArgumentTable,
                "params": OrderedDict((
                    ("x", {
                        "@type": ast.FormalParam,
                        "name": {
                            "@type": ast.IdentifierDef, "name": "x",
                            "begin": (1, 14), "end": (1, 15)
                        },
                        "default": None,
                        "port": {
                            "@type": ast.FunctionPort, "type": None,
                            "port": ast.FuncPortType.by_value,
                            "begin": (1, 14), "end": (1, 15)
                        }
                    }),
                    ("y", {
                        "@type": ast.FormalParam,
                        "name": {
                            "@type": ast.IdentifierDef, "name": "y",
                            "begin": (1, 17), "end": (1, 18)
                        },
                        "default": None,
                        "port": {
                            "@type": ast.FunctionPort,
                            "type": {
                                "@type": ast.TypeSpec,
                                "content": {
                                    "@type": ast.Identifier, "name": "int",
                                    "begin": (1, 20), "end": (1, 23)
                                }
                            },
                            "port": ast.FuncPortType.by_value,
                            "begin": (1, 17), "end": (1, 23)
                        }
                    }),
                    ("z", {
                        "name": {
                            "@type": ast.IdentifierDef, "name": "z",
                            "begin": (1, 31), "end": (1, 32)
                        },
                        "default": {
                            "@type": ast.IntLiteral, "value": 10,
                            "begin": (1, 33), "end": (1, 35)
                        },
                        "port": {
                            "@type": ast.FunctionPort, "type": None,
                            "port": ast.FuncPortType.const,
                            "begin": (1, 25), "end": (1, 32)
                        }
                    })
                ))
            },
            "returns": {
                "@type": ast.FunctionPort,
                "begin": (1, 40), "end": (1, 43),
                "port": ast.FuncPortType.by_value,
                "type": {
                    "@type": ast.TypeSpec,
                    "content": {
                        "@type": ast.Identifier, "name": "int",
                        "begin": (1, 40), "end": (1, 43)
                    }
                }
            },
            "body": [{"@type": ast.Pass, "begin": (2, 2), "end": (2, 6)}]
        }
    }),
    ("const def f(x: int = 20):\n pass", {
        "@type": ast.FuncDef, "begin": (1, 1), "end": (2, 6),
        "name": {
            "@type": ast.IdentifierDef, "name": "f",
            "begin": (1, 11), "end": (1, 12)
        },
        "data": {
            "@type": ast.ConstFuncData,
            "arg_table": {
                "@type": ast.ArgumentTable,
                "params": OrderedDict((
                    ("x", {
                        "@type": ast.FormalParam,
                        "name": {
                            "@type": ast.IdentifierDef, "name": "x",
                            "begin": (1, 13), "end": (1, 14)
                        },
                        "port": {
                            "@type": ast.FunctionPort,
                            "begin": (1, 13), "end": (1, 19),
                            "port": ast.FuncPortType.by_value,
                            "type": {
                                "@type": ast.TypeSpec,
                                "content": {
                                    "@type": ast.Identifier, "name": "int",
                                    "begin": (1, 16), "end": (1, 19),
                                }
                            }
                        },
                        "default": {
                            "@type": ast.IntLiteral, "value": 20,
                            "begin": (1, 22), "end": (1, 24)
                        }
                    }),
                ))
            },
            "returns": None,
            "body": [{"@type": ast.Pass, "begin": (2, 2), "end": (2, 6)}]
        }
    }),
    ("interface foo/bar:\n pass", {
        "@type": ast.InterfaceDef, "begin": (1, 1), "end": (2, 6),
        "path": "foo/bar",
        "body": [{"@type": ast.Pass, "begin": (2, 2), "end": (2, 6)}]
    }),
    ('interface "spam":\n pass', {
        "@type": ast.InterfaceDef, "begin": (1, 1), "end": (2, 6),
        "path": {
            "@type": ast.StrLiteral, "begin": (1, 11), "end": (1, 17),
            "content": {
                "@type": ast.FormattedStr,
                "content": ["spam"]
            }
        },
        "body": [{"@type": ast.Pass, "begin": (2, 2), "end": (2, 6)}]
    }),
    (
        "entity T extends Y:\n x: int\n pass\n new():\n  pass\n def f():\n"
        "  pass",
        {
            "@type": ast.EntityTemplateDef, "begin": (1, 1), "end": (7, 7),
            "name": {
                "@type": ast.IdentifierDef, "name": "T",
                "begin": (1, 8), "end": (1, 9)
            },
            "parents": [{
                "@type": ast.Identifier, "begin": (1, 18), "end": (1, 19),
                "name": "Y"
            }],
            "body": [
                {
                    "@type": ast.EntityField, "begin": (2, 2), "end": (2, 8),
                    "name": {
                        "@type": ast.IdentifierDef, "name": "x",
                        "begin": (2, 2), "end": (2, 3)
                    },
                    "type": {
                        "@type": ast.TypeSpec,
                        "content": {
                            "@type": ast.Identifier, "name": "int",
                            "begin": (2, 5), "end": (2, 8),
                        }
                    }
                },
                {"@type": ast.Pass, "begin": (3, 2), "end": (3, 6)},
                {
                    "@type": ast.EntityMethod,
                    "qualifier": ast.MethodQualifier.none,
                    "begin": (6, 2), "end": (7, 7),
                    "content": {
                        "@type": ast.FuncDef,
                        "name": {
                            "@type": ast.IdentifierDef, "name": "f",
                            "begin": (6, 6), "end": (6, 7)
                        },
                        "begin": (6, 2), "end": (7, 7),
                        "data": {
                            "@type": ast.NormalFuncData,
                            "arg_table": {
                                "@type": ast.ArgumentTable,
                                "params": OrderedDict()
                            },
                            "returns": None,
                            "body": [{"@type": ast.Pass,
                                      "begin": (7, 3), "end": (7, 7)}]
                        }
                    }
                }
            ],
            "new_method": {
                "@type": ast.NewMethod, "begin": (4, 2), "end": (5, 7),
                "new_begin": (4, 2), "new_end": (4, 5),
                "data": {
                    "@type": ast.NormalFuncData,
                    "arg_table": {
                        "@type": ast.ArgumentTable,
                        "params": OrderedDict()
                    },
                    "returns": None,
                    "body": [
                        {"@type": ast.Pass, "begin": (5, 3), "end": (5, 7)}
                    ]
                }
            }
        }
    ),
    ("x: int = 10", {
        "@type": ast.VarDef, "begin": (1, 1), "end": (1, 12),
        "target": {
            "@type": ast.IdentifierDef, "name": "x",
            "begin": (1, 1), "end": (1, 2)
        },
        "type": {
            "@type": ast.TypeSpec,
            "content": {
                "@type": ast.Identifier, "begin": (1, 4), "end": (1, 7),
                "name": "int"
            }
        },
        "value": {
            "@type": ast.IntLiteral, "value": 10,
            "begin": (1, 10), "end": (1, 12)
        }
    }),
    ("x := 10", {
        "@type": ast.AutoVarDef, "begin": (1, 1), "end": (1, 8),
        "target": {
            "@type": ast.IdentifierDef, "name": "x",
            "begin": (1, 1), "end": (1, 2)
        },
        "value": {
            "@type": ast.IntLiteral, "value": 10,
            "begin": (1, 6), "end": (1, 8)
        }
    }),
    ("x=10", {
        "@type": ast.Assign, "begin": (1, 1), "end": (1, 5),
        "target": {
            "@type": ast.Identifier, "begin": (1, 1), "end": (1, 2),
            "name": "x"
        },
        "value": {
            "@type": ast.IntLiteral, "value": 10,
            "begin": (1, 3), "end": (1, 5)
        }
    }),
    ("const x = 10", {
        "@type": ast.ConstDef, "begin": (1, 1), "end": (1, 13),
        "contents": [{
            "@type": ast.CompileTimeAssign,
            "name": {
                "@type": ast.IdentifierDef, "name": "x",
                "begin": (1, 7), "end": (1, 8)
            },
            "type": None,
            "value": {
                "@type": ast.IntLiteral, "begin": (1, 11), "end": (1, 13),
                "value": 10
            }
        }]
    }),
    ("const (a=1, b: int = 2)", {
        "@type": ast.ConstDef, "begin": (1, 1), "end": (1, 24),
        "contents": [
            {
                "@type": ast.CompileTimeAssign,
                "name": {
                    "@type": ast.IdentifierDef, "name": "a",
                    "begin": (1, 8), "end": (1, 9)
                },
                "type": None,
                "value": {
                    "@type": ast.IntLiteral, "begin": (1, 10), "end": (1, 11),
                    "value": 1
                }
            },
            {
                "@type": ast.CompileTimeAssign,
                "name": {
                    "@type": ast.IdentifierDef, "name": "b",
                    "begin": (1, 13), "end": (1, 14)
                },
                "type": {
                    "@type": ast.TypeSpec,
                    "content": {
                        "@type": ast.Identifier, "name": "int",
                        "begin": (1, 16), "end": (1, 19)
                    }
                },
                "value": {
                    "@type": ast.IntLiteral, "begin": (1, 22), "end": (1, 23),
                    "value": 2
                }
            }
        ]
    }),
    ("&x: int = y", {
        "@type": ast.ReferenceDef, "begin": (1, 1), "end": (1, 12),
        "content": {
            "@type": ast.CompileTimeAssign,
            "name": {
                "@type": ast.IdentifierDef, "name": "x",
                "begin": (1, 2), "end": (1, 3)
            },
            "type": {
                "@type": ast.TypeSpec,
                "content": {
                    "@type": ast.Identifier, "name": "int",
                    "begin": (1, 5), "end": (1, 8),
                }
            },
            "value": {
                "@type": ast.Identifier, "name": "y",
                "begin": (1, 11), "end": (1, 12),
            }
        }
    }),
    ("x *= 10", {
        "@type": ast.AugmentedAssign, "begin": (1, 1), "end": (1, 8),
        "target": {
            "@type": ast.Identifier, "begin": (1, 1), "end": (1, 2),
            "name": "x"
        },
        "operator": {"@type": ast.Mul, "begin": (1, 3), "end": (1, 5),},
        "value": {
            "@type": ast.IntLiteral, "begin": (1, 6), "end": (1, 8),
            "value": 10
        }
    }),
    ("/give ${foo} apple", {
        "@type": ast.Command, "begin": (1, 1), "end": (1, 19),
        "content": {
            "@type": ast.FormattedStr,
            "content": [
                "give ",
                {
                    "@type": ast.Identifier, "begin": (1, 9), "end": (1, 12),
                    "name": "foo"
                },
                " apple"
            ]
        }
    }),
    ("import foo.spam as bar", {
        "@type": ast.Import, "begin": (1, 1), "end": (1, 23),
        "meta": {
            "@type": ast.ModuleMeta,
            "path": ["foo", "spam"],
            "begin": (1, 8), "end": (1, 16)
        },
        "name": {
            "@type": ast.IdentifierDef, "name": "bar",
            "begin": (1, 20), "end": (1, 23)
        }
    }),
    ("from spam import ham as wood, tree", {
        "@type": ast.FromImport, "begin": (1, 1), "end": (1, 35),
        "meta": {
            "@type": ast.ModuleMeta,
            "path": ["spam"],
            "begin": (1, 6), "end": (1, 10)
        },
        "items": [
            {
                "@type": ast.ImportItem,
                "name": {
                    "@type": ast.IdentifierDef, "name": "ham",
                    "begin": (1, 18), "end": (1, 21)
                },
                "alias": {
                    "@type": ast.IdentifierDef, "name": "wood",
                    "begin": (1, 25), "end": (1, 29)
                }
            },
            {
                "@type": ast.ImportItem,
                "name": {
                    "@type": ast.IdentifierDef, "name": "tree",
                    "begin": (1, 31), "end": (1, 35)
                },
                "alias": {
                    "@type": ast.IdentifierDef, "name": "tree",
                    "begin": (1, 31), "end": (1, 35)
                }
            }
        ]
    }),
    ("from wood import *", {
        "@type": ast.FromImportAll, "begin": (1, 1), "end": (1, 19),
        "meta": {
            "@type": ast.ModuleMeta,
            "path": ["wood"],
            "begin": (1, 6), "end": (1, 10)
        },
        "star_begin": (1, 18), "star_end": (1, 19)
    }),
    ("for x in y:\n pass", {
        "@type": ast.For, "begin": (1, 1), "end": (2, 6),
        "name": {
            "@type": ast.IdentifierDef, "name": "x",
            "begin": (1, 5), "end": (1, 6)
        },
        "expr": {
            "@type": ast.Identifier, "begin": (1, 10), "end": (1, 11),
            "name": "y"
        },
        "body": [{"@type": ast.Pass, "begin": (2, 2), "end": (2, 6)}]
    }),
    ("struct T:\n x: int\n pass\n y: bool", {
        "@type": ast.StructDef, "begin": (1, 1), "end": (4, 9),
        "name": {
            "@type": ast.IdentifierDef, "name": "T",
            "begin": (1, 8), "end": (1, 9)
        },
        "bases": [],
        "body": [
            {
                "@type": ast.StructField, "begin": (2, 2), "end": (2, 8),
                "name": {
                    "@type": ast.IdentifierDef, "name": "x",
                    "begin": (2, 2), "end": (2, 3)
                },
                "type": {
                    "@type": ast.TypeSpec,
                    "content": {
                        "@type": ast.Identifier, "name": "int",
                        "begin": (2, 5), "end": (2, 8)
                    }
                }
            },
            {"@type": ast.Pass, "begin": (3, 2), "end": (3, 6)},
            {
                "@type": ast.StructField, "begin": (4, 2), "end": (4, 9),
                "name": {
                    "@type": ast.IdentifierDef, "name": "y",
                    "begin": (4, 2), "end": (4, 3)
                },
                "type": {
                    "@type": ast.TypeSpec,
                    "content": {
                        "@type": ast.Identifier, "name": "bool",
                        "begin": (4, 5), "end": (4, 9)
                    }
                }
            }
        ]
    }),
    ("result foo", {
        "@type": ast.Result, "begin": (1, 1), "end": (1, 11),
        "value": {
            "@type": ast.Identifier, "name": "foo",
            "begin": (1, 8), "end": (1, 11)
        }
    }),
    ("new()", {
        "@type": ast.NewCall, "begin": (1, 1), "end": (1, 6),
        "primary": None,
        "call_table": {"@type": ast.CallTable, "args": [], "keywords": {}}
    }),
    ("T.new()", {
        "@type": ast.NewCall, "begin": (1, 1), "end": (1, 8),
        "primary": {
            "@type": ast.Identifier, "name": "T",
            "begin": (1, 1), "end": (1, 2)
        },
        "call_table": {"@type": ast.CallTable, "args": [], "keywords": {}}
    }),
)

def _compare_ast_values(value, serialized) -> bool:
    if isinstance(value, ast.AST):
        assert isinstance(serialized, dict)
        if not ast_compare(value, serialized):
            return False
    elif isinstance(value, list):
        assert isinstance(serialized, list)
        if len(value) != len(serialized):
            return False
        for val, ser in zip(value, serialized):
            if not _compare_ast_values(val, ser):
                return False
    elif isinstance(value, dict):
        assert isinstance(serialized, dict)
        if len(value) != len(serialized):
            return False
        for key, val in value.items():
            if key not in serialized:
                return False
            ser = serialized[key]
            if not _compare_ast_values(val, ser):
                return False
    else:
        if value != serialized:
            return False
    return True

def ast_compare(node: ast.AST, serialized: Dict[str, Any]) -> bool:
    for field, value in serialized.items():
        if field == "@type":
            if not isinstance(node, value):
                return False
        else:
            if not _compare_ast_values(getattr(node, field), value):
                return False
    return True

class STArgReqToken(STArgRequirement):
    def __init__(self, tok_type: TokenType, value=None):
        self.tok_type = tok_type
        self.value = value

    def verify(self, arg: STArgument) -> bool:
        if not isinstance(arg, STToken):
            return False
        if arg.token.type is not self.tok_type:
            return False
        if arg.token.value != self.value:
            return False
        return True

class ParserTests(TestSuite):
    name = "parser"

    def parse(self, src: str, parser_method: str = "module") \
            -> Optional[ast.AST]:
        fe = self.owner.reader.add_fake_file(src)
        node = None
        with fe.open() as file:
            tokenizer = Tokenizer(file, fe, self.owner.diag, (1, 20, 10))
            parser = Parser(tokenizer)
            with self.owner.diag.capture_errors():
                node = getattr(parser, parser_method)()
        return node

    def assert_ast(self, src: str, serialized: Dict[str, Any],
                   parser_method: str):
        node = self.parse(src, parser_method)
        if node is None:
            raise TestFailure("assert_ast node failed to compile")
        self.assert_true(ast_compare(node, serialized), "AST did not match")

    @classmethod
    def init_class(cls):
        for i, (src, serialized) in enumerate(EXPR_SNIPPETS, start=1):
            func = partialmethod(
                cls.assert_ast, src=src, serialized=serialized,
                parser_method="expr"
            )
            setattr(cls, f"test_expr_snippet_{i}", func)
        for i, (src, serialized) in enumerate(STMT_SNIPPETS, start=1):
            func = partialmethod(
                cls.assert_ast, src=src, serialized=serialized,
                parser_method="statement"
            )
            setattr(cls, f"test_stmt_snippet_{i}", func)

    # Following test cases are for testing diagnostics

    def test_err_unexpected_token(self):
        with self.assert_diag(DiagnosticRequirement(
            id='unexpected-token',
            source=((1, 3), (1, 5)),
            args={'token': STArgReqToken(TokenType.identifier, "yz")}
        )):
            self.parse("x yz")
        with self.assert_diag(DiagnosticRequirement(
            id='unexpected-token',
            source=((1, 4), (1, 4)),
            args={'token': STArgReqToken(TokenType.new_line)}
        )):
            self.parse("x +")
        with self.assert_diag(DiagnosticRequirement(
            id='unexpected-token',
            source=((1, 8), (1, 14)),
            args={'token': STArgReqToken(TokenType.import_)}
        )):
            self.parse("inline import")

    def test_err_empty_block(self):
        with self.assert_diag(DiagnosticRequirement(
            id='empty-block',
            source=((1, 11), (1, 11)),
            args={}
        )):
            self.parse("def foo():")
        with self.assert_diag(DiagnosticRequirement(
            id='empty-block',
            source=((1, 11), (1, 12)),
            args={}
        )):
            self.parse("def foo():\n# foo\n  \\\n# bar")

    def test_err_non_default_arg_after_default(self):
        with self.assert_diag(DiagnosticRequirement(
            id='non-default-arg-after-default',
            source=((1, 15), (1, 16)),
            args={'arg': STArgReqSimpleValue('y')}
        )):
            self.parse("def foo(x=10, y: int):\n pass")

    def test_err_dont_know_arg_type(self):
        with self.assert_diag(DiagnosticRequirement(
            id='dont-know-arg-type',
            source=((1, 9), (1, 10)),
            args={'arg': STArgReqSimpleValue('x')}
        )):
            self.parse("def foo(x):\n pass")

    def test_err_duplicate_arg(self):
        with self.assert_diag(DiagnosticRequirement(
            id='duplicate-arg',
            source=((1, 17), (1, 18)),
            args={'arg': STArgReqSimpleValue('x')}
        )):
            self.parse("def foo(x: int, x: bool):\n pass")

    def test_err_duplicate_keyword_args(self):
        with self.assert_diag(DiagnosticRequirement(
            id='duplicate-keyword-args',
            source=((1, 18), (1, 19)),
            args={'arg': STArgReqSimpleValue('x')}
        )):
            self.parse("foo(1, x=2, y=3, x=4)")

    def test_err_invalid_func_port(self):
        with self.assert_diag(DiagnosticRequirement(
            id='invalid-func-port',
            source=((1, 7), (1, 8)),
            args={'port': STArgReqSimpleValue(ast.FuncPortType.by_reference)}
        )):
            self.parse("def f(&x):\n pass")
        with self.assert_diag(DiagnosticRequirement(
            id='invalid-func-port',
            source=((1, 7), (1, 12)),
            args={'port': STArgReqSimpleValue(ast.FuncPortType.const)}
        )):
            self.parse("def f(const x):\n pass")
        with self.assert_diag(DiagnosticRequirement(
            id='invalid-func-port',
            source=((1, 13), (1, 18)),
            args={'port': STArgReqSimpleValue(ast.FuncPortType.const)}
        )):
            self.parse("const def f(const x):\n pass")

    def test_err_const_new_method(self):
        with self.assert_diag(DiagnosticRequirement(
            id='const-new-method',
            source=((2, 2), (2, 11)),
            args={}
        )):
            self.parse("entity X:\n const new():\n  pass")

    def test_err_non_static_const_method(self):
        with self.assert_diag(DiagnosticRequirement(
            id='non-static-const-method',
            source=((2, 12), (2, 13)),
            args={}
        )):
            self.parse("entity X:\n const def f():\n  pass")

    def test_err_invalid_var_def(self):
        with self.assert_diag(DiagnosticRequirement(
            id='invalid-var-def',
            source=((1, 1), (1, 6)),
            args={}
        )):
            self.parse("x + 1: int = 2")
        with self.assert_diag(DiagnosticRequirement(
            id='invalid-var-def',
            source=((1, 1), (1, 5)),
            args={}
        )):
            self.parse("x[1] := 2")

    def test_err_positional_arg_after_keyword(self):
        with self.assert_diag(DiagnosticRequirement(
            id='positional-arg-after-keyword',
            source=((1, 11), (1, 14)),
            args={}
        )):
            self.parse("f(1, x=2, 3+4)")

    def test_err_multiple_new_methods(self):
        with self.assert_diag(DiagnosticRequirement(
            id='multiple-new-methods',
            source=((5, 9), (5, 12)),
            args={'nnews': STArgReqSimpleValue(2)}
        )), \
            self.assert_diag(DiagnosticRequirement(
            id='multiple-new-methods-note',
            source=((2, 2), (2, 5)),
            args={}
        )):
            self.parse("entity X:\n new():\n  pass\n x: int\n"
                       " inline new():\n  pass")
