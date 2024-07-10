"""Unit test for Acacia."""

from typing import (
    Optional, Union, NamedTuple, Mapping, List, Type, TextIO, Tuple, Dict,
    Iterable
)
from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from sys import stdout
from traceback import print_exception

from acaciamc.diagnostic import Diagnostic, DiagnosticsManager
from acaciamc.reader import Reader
from acaciamc.utils.ansi import AnsiColor, AnsiStyle, ansi
from acaciamc.utils.str_template import (
    STArgument, STInt, STStr, STEnum, substitute, DisplayableEnum
)

class TrackedDiagnosticsManager(DiagnosticsManager):
    def __init__(self, owner: "TestManager"):
        super().__init__(owner.reader, stream=None)
        self.owner = owner

    def push_diagnostic(self, diag: Diagnostic,
                        notes: Optional[Iterable[Diagnostic]] = None):
        self.owner.note_diag(diag)
        return super().push_diagnostic(diag, notes)

class STArgRequirement(metaclass=ABCMeta):
    @abstractmethod
    def verify(self, arg: STArgument) -> bool:
        pass

class STArgReqSimpleValue(STArgRequirement):
    def __init__(self, value: Union[int, str, DisplayableEnum]):
        self.value = value

    def verify(self, arg: STArgument) -> bool:
        if isinstance(self.value, DisplayableEnum):
            return isinstance(arg, STEnum) and arg.enum_value is self.value
        elif isinstance(self.value, int):
            return isinstance(arg, STInt) and arg.value == self.value
        elif isinstance(self.value, str):
            return isinstance(arg, STStr) and arg.value == self.value
        assert False

class DiagnosticRequirement(NamedTuple):
    id: Optional[str] = None
    source: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    args: Optional[Mapping[str, STArgRequirement]] = None

    def matches(self, diag: Diagnostic) -> bool:
        if self.id is not None and diag.id != self.id:
            return False
        if self.source is not None:
            pos1, pos2 = self.source
            if pos1 != diag.source.begin.pos or pos2 != diag.source.end.pos:
                return False
        if self.args is not None:
            # Keys must exactly match
            if self.args.keys() != diag.args.keys():
                return False
            for name, argreq in self.args.items():
                arg = diag.args[name]
                if not argreq.verify(arg):
                    return False
        return True

class TestFailure(Exception):
    pass

class TestLog(NamedTuple):
    case_name: str
    failure: Optional[TestFailure]

class TestSuite:
    """
    A collection of testcases.
    Each testcase should be a method whose name starts with
    `case_prefix`. 
    """

    # To be set by subclasses:
    name: str
    # Attributes (when the class is created) whose name begin with
    # `case_prefix` are considered test cases.
    case_prefix: str = "test_"
    # Test case name without `case_prefix`. Set in `__init_subclass__`:
    case_names: List[str]

    def __init__(self, owner: "TestManager"):
        self.owner = owner
        self.logs: List[TestLog] = []

    def __init_subclass__(cls, **kwds):
        super().__init_subclass__(**kwds)
        # Make sure subclass set `name`
        if not hasattr(cls, "name"):
            raise AttributeError(f"{cls!r} did not set 'name'")
        # Init class
        cls.init_class()
        # Collect tests
        cls.case_names = []
        for method in dir(cls):
            if not method.startswith(cls.case_prefix):
                continue
            cls.case_names.append(method[len(cls.case_prefix):])

    @classmethod
    def init_class(cls):
        """
        Called at class creation; intended to be used to dynamically
        create testcases by adding methods to `cls`.
        """
        pass

    def setup(self):
        """Called before the whole test suite is run."""
        pass

    def teardown(self):
        """
        Called after the whole test suite finished.
        Will always run if `setup` successfully returned.
        """
        pass

    @contextmanager
    def assert_diag(self, req: DiagnosticRequirement):
        self.owner.diag_reqs.insert(0, req)
        self.owner.diag_received.insert(0, False)
        yield
        received = self.owner.diag_received.pop(0)
        if not received:
            raise TestFailure(f'did not receive diagnostic {req!r}')
        self.owner.diag_reqs.pop(0)

    def assert_true(self, v: object, message: str):
        if not v:
            raise TestFailure(message)

    def assert_false(self, v: object, message: str):
        if v:
            raise TestFailure(message)

test_log_messages: Dict[str, str] = {
    'case-failed': "Case ${case} failed\n",
    'suite-result': "${suite}: ${npassed}/${ncases} case${npassed plural} "
        "passed\n",
    'overall-result': "${npassed}/${nsuites} suite${npassed plural} passed\n",
}

class TestManager:
    def __init__(self):
        self.reader = Reader()
        self.diag = TrackedDiagnosticsManager(self)
        self.diag_reqs: List[DiagnosticRequirement] = []
        self.diag_received: List[bool] = []
        self.suites: List[TestSuite] = []

    def note_diag(self, diag: Diagnostic):
        it = enumerate(zip(self.diag_reqs, self.diag_received))
        for i, (req, received) in it:
            if received:
                continue
            if req.matches(diag):
                self.diag_received[i] = True
                break
        else:
            raise TestFailure(f'unexpected diagnostic {diag!r}')

    def register(self, suite_class: Type[TestSuite]):
        self.suites.append(suite_class(self))

    def run(self):
        for suite in self.suites:
            suite.setup()
            try:
                for name in suite.case_names:
                    func = getattr(suite, suite.case_prefix + name)
                    try:
                        func()
                    except TestFailure as err:
                        failure = err
                    else:
                        failure = None
                    suite.logs.append(TestLog(name, failure))
            finally:
                suite.teardown()

    def print_log(self, file: TextIO = stdout):
        nsuites = len(self.suites)
        nsuite_passed = 0
        for suite in self.suites:
            ncases = len(suite.logs)
            npassed = 0
            for log in suite.logs:
                if log.failure is None:
                    npassed += 1
                    continue
                with ansi(file, AnsiStyle.UNDERLINE):
                    file.write(substitute(
                        test_log_messages["case-failed"],
                        {'case': STStr(f"{suite.name}.{log.case_name}")}
                    ))
                with ansi(file, AnsiColor.RED):
                    print_exception(log.failure, file=file)
            with ansi(file, AnsiStyle.BOLD):
                file.write(substitute(
                    test_log_messages["suite-result"],
                    {'suite': STStr(suite.name),
                     'npassed': STInt(npassed),
                     'ncases': STInt(ncases)}
                ))
            if npassed == ncases:
                nsuite_passed += 1
        with ansi(file, AnsiStyle.BOLD):
            file.write(substitute(
                test_log_messages["overall-result"],
                {'npassed': STInt(nsuite_passed),
                 'nsuites': STInt(nsuites)}
            ))

def main():
    """Entry of Acacia unit tests."""
    import glob
    import os
    from importlib import import_module
    from time import perf_counter

    def my_print(msg: str):
        with ansi(stdout, AnsiStyle.BOLD):
            print(msg)

    t1 = perf_counter()
    manager = TestManager()
    # Treat all files starting with "test_" as test files.
    root = os.path.dirname(__file__)
    for file in glob.iglob("**/test_*.py", recursive=True, root_dir=root):
        # Work out the module name from file name (XXX do we have a
        # better way to do this?)
        file = file[:-3]  # len(".py") == 3
        mod_name = file.replace(os.sep, '.')
        if os.altsep is not None:
            mod_name = mod_name.replace(os.altsep, '.')
        module = import_module(f"acaciamc.test.{mod_name}")
        for objname in dir(module):
            obj = getattr(module, objname)
            if (isinstance(obj, type) and issubclass(obj, TestSuite)
                    and obj is not TestSuite):
                manager.register(obj)
    t2 = perf_counter()
    my_print(f"Test discovery finished in {t2 - t1:.3g} seconds")
    manager.run()
    manager.print_log()
    my_print(f"Tests finished in {perf_counter() - t2:.3g} seconds")
