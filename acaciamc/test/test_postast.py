"""Unit tests for post AST visitor."""

from typing import Tuple, Optional
from tempfile import TemporaryDirectory
import os
import shutil

from acaciamc.test import TestSuite, DiagnosticRequirement, STArgReqSimpleValue
from acaciamc.postast import ASTForest
import acaciamc.ast as ast

MC_VERSION = (1, 20, 10)

DEFINITIONS = (
    # Note that the patterns here are expected to produce a single AST
    # node (for example, "x := 1\nx = 2" would cause problems)
    '{v}: int = 1',
    "{v} := 10",
    'const {v} = "x"',
    "&{v} = 1",
    "def {v}():\n pass",
    "inline def {v}(x):\n x",
    "const def {v}():\n pass",
    "entity {v}:\n pass",
    # `_test_dummy` is a dummy file in the standard library:
    "import _test_dummy as {v}",
    "from _test_dummy import x as {v}",
    "struct {v}:\n pass",
)
SCOPES = (
    # Use one space indentation before {b}
    "if True:\n {b}",
    "while True:\n {b}",
    "def {x}():\n {b}",
    "inline def {x}():\n {b}",
    "const def {x}():\n {b}",
    "interface foo:\n {b}",
    # Add {x} at last to suppress `unused-name`
    "for {x} in {{}}:\n {b}\n {x}",
)

class PostASTImportTests(TestSuite):
    name = 'postast_import'

    def setup(self):
        self.tempdir = TemporaryDirectory()

    def teardown(self):
        self.tempdir.cleanup()

    def parse_forest(self, main_content: str, *files: Tuple[str, str]):
        """
        Given content of main file `main_content` and all the other
        `files` in the form of (file path, file content) tuple, parse
        the main file and return the `modules` of the `ASTForest` as
        parsing result.
        """
        # Delete old files, in case they affect `import`s.
        for path in os.listdir(self.tempdir.name):
            fullpath = os.path.join(self.tempdir.name, path)
            if os.path.isdir(fullpath):
                shutil.rmtree(fullpath)
            else:
                os.remove(fullpath)
        # Set up files
        for path, content in files:
            fullpath = os.path.join(self.tempdir.name, path)
            os.makedirs(os.path.dirname(fullpath), exist_ok=True)
            with open(fullpath, "w", encoding="utf-8") as file:
                file.write(content)
            self.owner.reader.delete_real_file_cache(fullpath)
        mainpath = os.path.join(self.tempdir.name, "main.aca")
        with open(mainpath, "w", encoding="utf-8") as file:
            file.write(main_content)
        self.owner.reader.delete_real_file_cache(mainpath)
        # Start parsing
        main_entry = self.owner.reader.get_real_file(mainpath)
        forest = ASTForest(self.owner.reader, self.owner.diag, main_entry,
                           mc_version=MC_VERSION)
        return forest.modules

    def test_import_module(self):
        modules = self.parse_forest(
            "import spam",
            ("spam.aca", "# This is spam")
        )
        self.assert_true("__main__" in modules,
                         "expected __main__ to be loaded")
        self.assert_true("spam" in modules, "expected spam to be loaded")
        self.assert_false(modules["spam"].ast.body,
                          "spam body should be empty")
        main_body = modules["__main__"].ast.body
        self.assert_true(len(main_body) == 1,
                         "main body should have exactly 1 statement")
        main_stmt = main_body[0]
        self.assert_true(
            isinstance(main_stmt, ast.Import)
                and main_stmt.meta.path == ["spam"],
            "first statement in main body should be 'import spam'"
        )
        # Make sure other kinds of imports work
        modules = self.parse_forest(
            "from ham import bar",
            ("ham.aca", "bar := 1")
        )
        self.assert_true("__main__" in modules,
                         "expected __main__ to be loaded")
        self.assert_true("ham" in modules, "expected spam to be loaded")
        self.assert_true(len(modules["ham"].ast.body) == 1,
                         "ham body should have exactly 1 statement")

    def test_import_package(self):
        modules = self.parse_forest(
            "from foo.bar import spam",
            ("foo/__init__.aca", "# Dummy"),
            ("foo/bar.aca", "spam := 1")
        )
        self.assert_true("__main__" in modules,
                         "expected __main__ to be loaded")
        self.assert_true("foo" in modules,
                         "expected foo package to be loaded")
        self.assert_true("foo.bar" in modules,
                         "expected foo.bar to be loaded")
        modules = self.parse_forest(
            "from foo import bar\n"
            "from foo.spam.ham import *",
            ("foo/__init__.aca", "bar := 10"),
            ("foo/bar.aca", "# Not loaded"),
            ("foo/spam/__init__.aca", "import foo"),
            ("foo/spam/ham.aca", "# spam/ham"),
        )
        self.assert_true("foo" in modules,
                         "expected foo package to be loaded")
        self.assert_true("foo.bar" not in modules,
                         "foo.bar should not be loaded")
        self.assert_true("foo.spam" in modules,
                         "expected foo.spam package to be loaded")
        self.assert_true("foo.spam.ham" in modules,
                         "expected foo.spam.ham to be loaded")

    def test_main_module(self):
        self.parse_forest(
            "x := 10\n"
            "import foo",
            ("foo.aca", "from __main__ import x")
        )

    def test_import_error_module(self):
        with self.assert_diag(DiagnosticRequirement(
            "invalid-char",
            ((1, 1), (1, 2)),
            args={"char": STArgReqSimpleValue("$")}
        )), \
            self.assert_diag(DiagnosticRequirement(
            "imported-here",
            ((1, 8), (1, 11)),
            args={}
        )):
            self.parse_forest(
                "import foo",
                ("foo.aca", "$")
            )

    def test_err_module_not_found(self):
        with self.assert_diag(DiagnosticRequirement(
            "module-not-found",
            ((1, 8), (1, 22)),
            args={"module": STArgReqSimpleValue("does_not_exist")}
        )):
            self.parse_forest("import does_not_exist")
        with self.assert_diag(DiagnosticRequirement(
            "module-not-found",
            ((1, 8), (1, 17)),
            args={"module": STArgReqSimpleValue("text_file")}
        )):
            self.parse_forest("import text_file", ("text_file.txt", ""))
        with self.assert_diag(DiagnosticRequirement(
            "module-not-found",
            ((1, 8), (1, 23)),
            args={"module": STArgReqSimpleValue("invalid_package")}
        )):
            self.parse_forest("import invalid_package",
                              ("invalid_package/__init__.txt", ""))
        with self.assert_diag(DiagnosticRequirement(
            "module-not-found",
            ((1, 8), (1, 25)),
            args={"module": STArgReqSimpleValue("foo.no_sub_module")}
        )):
            self.parse_forest("import foo.no_sub_module",
                              ("foo/__init__.aca", ""))
        with self.assert_diag(DiagnosticRequirement(
            "module-not-found",
            ((1, 8), (1, 30)),
            args={"module": STArgReqSimpleValue("foo.no_subpackage.spam")}
        )):
            self.parse_forest("import foo.no_subpackage.spam",
                              ("foo/__init__.aca", ""),
                              ("foo/spam.aca", ""))

    def test_warn_partial_wildcard_import(self):
        with self.assert_diag(DiagnosticRequirement(
            "partial-wildcard-import",
            ((1, 1), (1, 23)),
            args={"module": STArgReqSimpleValue("__main__")}
        )), \
            self.assert_diag(DiagnosticRequirement(
            "imported-here",
            ((1, 8), (1, 11)),
            args={}
        )):
            self.parse_forest(
                "import foo",
                ("foo.aca", "from __main__ import *")
            )

class PostASTSymbolTests(TestSuite):
    name = 'postast_symbol'

    def parse(self, source: str) -> Optional[ast.Module]:
        """Parse `source` to an annotated AST. Return None if failed."""
        main_entry = self.owner.reader.add_fake_file(source)
        forest = ASTForest(self.owner.reader, self.owner.diag, main_entry,
                           mc_version=MC_VERSION)
        if forest.succeeded:
            return forest.modules["__main__"].ast
        return None

    def test_symbol_simple(self):
        NAME = "some_name"
        for definition in DEFINITIONS:
            defi = definition.format(v=NAME)
            # TODO When builtins are added, remove the dummy `const int`:
            # Last `int` to suppress `unused-name` WARNING:
            s = f"const int = 1\n{defi}\nif True:\n {NAME}\n{NAME}\nint"
            mod = self.parse(s)
            assert mod  # Test should fail immediately if a diag is issued
            # First NAME
            ifnode = mod.body[2]
            assert isinstance(ifnode, ast.If)
            exprstmtnode = ifnode.body[0]
            assert isinstance(exprstmtnode, ast.ExprStatement)
            exprnode = exprstmtnode.value
            assert isinstance(exprnode, ast.Identifier)
            sym1 = exprnode.annotation
            # Second NAME
            exprstmtnode = mod.body[3]
            assert isinstance(exprstmtnode, ast.ExprStatement)
            exprnode = exprstmtnode.value
            assert isinstance(exprnode, ast.Identifier)
            sym2 = exprnode.annotation
            # Compare
            self.assert_true(sym1 is sym2,
                             f"Symbols for the two {NAME} are not the same")

    def test_symbol_complex(self):
        mod = self.parse(
            "x := 1\n"
            "x\n"
            "if True:\n"
            "    x\n"
            "    x := 2\n"
            "    if True:\n"
            "        x := 3\n"
            "        x\n"
            "    x\n"
            "    if True:\n"
            "        x\n"
            "        x := 4\n"
            "        x\n"
            "    x\n"
            "x\n"
        )
        assert mod  # Test should fail immediately if a diag is issued
        # Toplevel
        def1 = mod.body[0]
        exprnode1 = mod.body[1]
        ifnode1 = mod.body[2]
        exprnode2 = mod.body[3]
        assert isinstance(def1, ast.AutoVarDef)
        assert isinstance(exprnode1, ast.ExprStatement)
        assert isinstance(exprnode2, ast.ExprStatement)
        assert isinstance(ifnode1, ast.If)
        expr1 = exprnode1.value
        expr2 = exprnode2.value
        assert isinstance(expr1, ast.Identifier)
        assert isinstance(expr2, ast.Identifier)
        sym1_0 = def1.target.annotation
        sym1_1 = expr1.annotation
        sym1_2 = expr2.annotation
        # Under "if"
        exprnode3 = ifnode1.body[0]
        def2 = ifnode1.body[1]
        ifnode2 = ifnode1.body[2]
        exprnode4 = ifnode1.body[3]
        ifnode3 = ifnode1.body[4]
        exprnode5 = ifnode1.body[5]
        assert isinstance(def2, ast.AutoVarDef)
        assert isinstance(exprnode3, ast.ExprStatement)
        assert isinstance(exprnode4, ast.ExprStatement)
        assert isinstance(exprnode5, ast.ExprStatement)
        assert isinstance(ifnode2, ast.If)
        assert isinstance(ifnode3, ast.If)
        expr3 = exprnode3.value
        expr4 = exprnode4.value
        expr5 = exprnode5.value
        assert isinstance(expr3, ast.Identifier)
        assert isinstance(expr4, ast.Identifier)
        assert isinstance(expr5, ast.Identifier)
        sym1_3 = expr3.annotation
        sym2_0 = def2.target.annotation
        sym2_1 = expr4.annotation
        sym2_2 = expr5.annotation
        # Under first inner "if"
        def3 = ifnode2.body[0]
        exprnode6 = ifnode2.body[1]
        assert isinstance(def3, ast.AutoVarDef)
        assert isinstance(exprnode6, ast.ExprStatement)
        expr6 = exprnode6.value
        assert isinstance(expr6, ast.Identifier)
        sym3_0 = def3.target.annotation
        sym3_1 = expr6.annotation
        # Under second inner "if"
        exprnode7 = ifnode3.body[0]
        def4 = ifnode3.body[1]
        exprnode8 = ifnode3.body[2]
        assert isinstance(def4, ast.AutoVarDef)
        assert isinstance(exprnode7, ast.ExprStatement)
        assert isinstance(exprnode8, ast.ExprStatement)
        expr7 = exprnode7.value
        expr8 = exprnode8.value
        assert isinstance(expr7, ast.Identifier)
        assert isinstance(expr8, ast.Identifier)
        sym2_3 = expr7.annotation
        sym4_0 = def4.target.annotation
        sym4_1 = expr8.annotation
        # Assertions
        self.assert_true(sym1_0 is sym1_1 is sym1_2 is sym1_3,
                         "Inconsistent first symbol")
        self.assert_true(sym2_0 is sym2_1 is sym2_2 is sym2_3,
                         "Inconsistent second symbol")
        self.assert_true(sym3_0 is sym3_1,
                         "Inconsistent third symbo")
        self.assert_true(sym4_0 is sym4_1,
                         "Inconsistent fourth symbo")
        self.assert_true(
            sym1_1 is not sym2_1
            and sym1_1 is not sym3_1
            and sym1_1 is not sym4_1
            and sym2_1 is not sym3_1
            and sym2_1 is not sym4_1
            and sym3_1 is not sym4_1,
            "Four symbols are not all different"
        )

    def test_wildcard_import(self):
        with self.assert_diag(DiagnosticRequirement(
            "undefined-name",
            ((4, 1), (4, 3)),
            {"name": STArgReqSimpleValue("_z")}
        )):
            self.parse(
                "from _test_dummy import *\n"
                "x\n"
                "y\n"
                "_z\n"
            )

    def test_from_import(self):
        with self.assert_diag(DiagnosticRequirement(
            "undefined-name",
            ((4, 1), (4, 2)),
            {"name": STArgReqSimpleValue("x")}
        )):
            self.parse(
                "from _test_dummy import x as q, _z\n"
                "q\n"
                "_z\n"
                "x\n"
            )

    def test_symbol_complex_if(self):
        mod = self.parse(
            "x := 2\n"
            "if True:\n"
            "    x\n"
            "else:\n"
            "    x\n"
            "    x := 2\n"
            "    x\n"
        )
        assert mod  # Test should fail immediately if a diag is issued
        def1 = mod.body[0]
        ifnode = mod.body[1]
        assert isinstance(def1, ast.AutoVarDef)
        assert isinstance(ifnode, ast.If)
        exprnode1 = ifnode.body[0]
        exprnode2 = ifnode.else_body[0]
        def2 = ifnode.else_body[1]
        exprnode3 = ifnode.else_body[2]
        assert isinstance(def2, ast.AutoVarDef)
        assert isinstance(exprnode1, ast.ExprStatement)
        assert isinstance(exprnode2, ast.ExprStatement)
        assert isinstance(exprnode3, ast.ExprStatement)
        expr1 = exprnode1.value
        expr2 = exprnode2.value
        expr3 = exprnode3.value
        assert isinstance(expr1, ast.Identifier)
        assert isinstance(expr2, ast.Identifier)
        assert isinstance(expr3, ast.Identifier)
        sym1_0 = def1.target.annotation
        sym1_1 = expr1.annotation
        sym1_2 = expr2.annotation
        sym2_0 = def2.target.annotation
        sym2_1 = expr3.annotation
        self.assert_true(sym1_0 is sym1_1 is sym1_2,
                         "Inconsistent first symbol")
        self.assert_true(sym2_0 is sym2_1,
                         "Inconsistent second symbol")
        self.assert_true(sym1_1 is not sym2_1,
                         "Two symbols should be different")

    def test_all_scopes(self):
        # To verify all the constructs in `SCOPES` create a new scope,
        # we check if we could redefine `x`.
        for scope in SCOPES:
            scope_f = scope.format(b="x := 2\n x", x="some_name")
            self.parse(f"x := 1\n{scope_f}\n")

    def test_non_scope(self):
        self.parse("entity T:\n def f():\n  f := 30\n  f\nf := 10")
        self.parse("entity T:\n f: None\nf := 20")
        self.parse("struct T:\n x: None\nx := 0")

    def test_err_undefined_name(self):
        with self.assert_diag(DiagnosticRequirement(
            "undefined-name",
            ((1, 1), (1, 2)),
            args={"name": STArgReqSimpleValue("x")}
        )):
            self.parse("x")
        with self.assert_diag(DiagnosticRequirement(
            "undefined-name",
            ((4, 1), (4, 2)),
            args={"name": STArgReqSimpleValue("x")}
        )):
            self.parse("if True:\n  x := 2\n  x\nx")

    def test_err_name_redefinition(self):
        with self.assert_diag(DiagnosticRequirement(
            "name-redefinition",
            ((1, 31), (1, 32)),
            args={"name": STArgReqSimpleValue("x")}
        )), \
            self.assert_diag(DiagnosticRequirement(
            "name-redefinition-note",
            ((1, 25), (1, 26))
        )):
            self.parse("from _test_dummy import x, y, x\nx\ny")
        with self.assert_diag(DiagnosticRequirement(
            "name-redefinition",
            ((5, 1), (5, 2)),
            args={"name": STArgReqSimpleValue("x")}
        )), \
            self.assert_diag(DiagnosticRequirement(
            "name-redefinition-note",
            ((1, 1), (1, 2))
        )):
            self.parse("x := 20\nif True:\n  x := 30\n  x\nx := 20\nx")

    def test_err_cannot_import_name(self):
        with self.assert_diag(DiagnosticRequirement(
            "cannot-import-name",
            ((1, 25), (1, 28)),
            args={"name": STArgReqSimpleValue("foo"),
                  "module": STArgReqSimpleValue("_test_dummy")}
        )):
            self.parse("from _test_dummy import foo")

    def test_warn_unused_name(self):
        with self.assert_diag(DiagnosticRequirement(
            "unused-name",
            ((2, 2), (2, 3)),
            args={"name": STArgReqSimpleValue("x")}
        )):
            self.parse("if True:\n x := 10")
