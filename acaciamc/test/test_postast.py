"""Unit tests for post AST visitor."""

from typing import Tuple
from tempfile import TemporaryDirectory
import os

from acaciamc.test import TestSuite, DiagnosticRequirement, STArgReqSimpleValue
from acaciamc.postast import ASTForest
import acaciamc.ast as ast

class PostASTTests(TestSuite):
    name = 'postast'

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
                           mc_version=(1, 20, 10))
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
