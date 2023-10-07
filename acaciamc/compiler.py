"""The main compiler of Acacia.
It assembles files and classes together and write output.
"""

__all__ = ['Compiler']

from typing import Tuple, Union, Optional
import os
from contextlib import contextmanager

from acaciamc.ast import ModuleMeta
from acaciamc.constants import Config
from acaciamc.error import *
from acaciamc.tokenizer import Tokenizer
from acaciamc.parser import Parser
from acaciamc.mccmdgen.generator import Generator
from acaciamc.mccmdgen.expression import *
from acaciamc.mccmdgen.symbol import SymbolTable
from acaciamc.mccmdgen.optimizer import Optimizer
import acaciamc.mccmdgen.cmds as cmds

class OutputManager(cmds.FunctionsManager):
    def __init__(self):
        super().__init__("%s/init" % Config.function_folder)
        self._lib_count = 0

    def new_file(self, file: cmds.MCFunctionFile, path: str):
        file.set_path("%s/%s" % (Config.function_folder, path))
        self.files.append(file)

    def add_lib(self, file: cmds.MCFunctionFile):
        self._lib_count += 1
        self.new_file(file, "lib/acalib%d" % self._lib_count)

class OutputOptimized(OutputManager, Optimizer):
    def is_volatile(self, slot: cmds.ScbSlot) -> bool:
        if super().is_volatile(slot):
            return True
        # Scores on user custom scoreboards are volatile
        return slot.objective != Config.scoreboard

    def entry_files(self):
        entries = tuple(
            (Config.function_folder + "/%s" % path)
            for path in ("interface/", "load", "tick")
            # "init" is automatically added
        )
        for file in self.files:
            if file.get_path().startswith(entries):
                yield file

    @property
    def max_inline_file_size(self) -> int:
        return Config.max_inline_file_size

    def dont_inline_execute_call(self, file: cmds.MCFunctionFile) -> bool:
        # Expanding /execute function calls in tick.mcfunction can
        # decrease performance badly.
        return file.get_path() == Config.function_folder + "/tick"

class Compiler:
    """Start compiling the project
    A Compiler manage the resources in the compile task and
    connect the steps to compile: Tokenizer -> Parser -> Generator.
    """
    def __init__(self, main_path: str, open_args={}):
        """
        main_path: path of main source file
        open_args: args to pass to builtin `open`.
        """
        self.main_dir, _ = os.path.split(main_path)
        self.main_dir = os.path.realpath(self.main_dir)
        ACACIA = os.path.realpath(os.path.dirname(__file__))
        self.path = [
            os.path.join(ACACIA, 'modules'),  # buitlin modules
            self.main_dir  # find in program entry (main file)
        ]  # modules will be found in these directories
        self.OPEN_ARGS = open_args
        if Config.optimizer:
            self.output_mgr = OutputOptimized()
        else:
            self.output_mgr = OutputManager()
        self.file_main = cmds.MCFunctionFile()  # load program
        self.file_tick = cmds.MCFunctionFile()  # runs every tick
        self.output_mgr.new_file(self.file_main, "load")
        self.output_mgr.new_file(self.file_tick, "tick")
        self.current_generator = None  # the Generator that is running
        # vars to record the resources that are applied
        self._score_max = 0  # max id of score allocated
        self._scoreboard_max = 0  # max id of scoreboard allocated
        self._entity_max = 0  # max id of entity name allocated
        self._entity_tag_max = 0  # max id of entity tag allocated
        self._free_tmp_score = []  # free tmp scores (see `allocate_tmp`)
        self._current_file = None  # str; Path of current parsing file
        self._cached_modules = {}  # loaded modules are cached here
        self._loading_files = []  # paths of Acacia modules that are loading

        # --- BUILTINS ---
        self.builtins = SymbolTable()
        self.base_template = EntityTemplate(
            name="Object",
            field_types={}, field_metas={},
            methods={}, parents=[], metas={}, compiler=self
        )
        # builtin types
        for name, cls in (
            ('int', IntType),
            ('bool', BoolType),
            ('Pos', PosType),
            ('Rot', RotType),
            ('Offset', PosOffsetType),
            ('Engroup', EGroupType),
            ('Enfilter', EFilterType),
            ('array', ArrayType),
            ('map', MapType),
            ('AbsPos', AbsPosType),
        ):
            self.builtins.set(name, cls(self))
        # builtin names
        for name, value in (
            ('Object', self.base_template),
        ):
            self.builtins.set(name, value)

        # --- START COMPILE ---
        ## comment on load.mcfunction
        self.file_main.write_debug(
            '## Usage: Run this Acacia project',
            '## Execute this before using interfaces!!!'
        )
        ## start
        with self._load_generator(main_path) as generator:
            generator.parse()

    def output(self, path: str):
        """Output result to `path`
        e.g. when `path` is "a/b", main file is generated at
        "a/b/<Config.function_folder>/load.mcfunction".
        """
        if isinstance(self.output_mgr, OutputOptimized):
            self.output_mgr.optimize()
        self.output_mgr.generate_init_file()  # do this after optimize
        # Mcfunctions
        for file in self.output_mgr.files:
            if file.has_content():
                self._write_mcfunction(file, path)
        # tick.json
        if self.file_tick.has_content():
            self._write_file(
                '{"values": ["%s/tick"]}' % Config.function_folder,
                os.path.join(path, 'tick.json')
            )

    def raise_error(self, error: Error):
        self.current_generator.fix_error_location(error)
        error.set_file(self._current_file)
        raise error

    def add_file(self, file: cmds.MCFunctionFile, path: Optional[str] = None):
        """Add a file to project. If file's path is not set, then it
        will go to "lib" folder.
        """
        if path is None:
            self.output_mgr.add_lib(file)
        else:
            self.output_mgr.new_file(file, path)

    # -- About allocation --

    def allocate(self) -> cmds.ScbSlot:
        """Apply for a new score."""
        return self.output_mgr.allocate()

    def allocate_tmp(self) -> cmds.ScbSlot:
        """Apply for a temporary score
        NOTE Only do this when you are really using a TEMPORARY var
        because the var returned might have been used by others
        NOTE Temporary vars are only available within 1 statement
        when it comes to next statement, current vars are deleted.
        """
        if self._free_tmp_score:
            # if there are free vars in list, reuse them
            res = self._free_tmp_score.pop()
        else:
            # else, allocate a new one
            res = self.allocate()
        self.current_generator.current_tmp_scores.append(res)
        return res

    def free_tmp(self, slot: cmds.ScbSlot):
        """Free the tmp var allocated by method `allocate_tmp`.
        NOTE This is called automatically.
        """
        self._free_tmp_score.append(slot)

    def add_int_const(self, value: int) -> IntVar:
        """Sometimes a constant is needed when calculating in MC
        e.g. `a * 2`, we need a score to store 2, so that we can use
             `scoreboard operation ... *= const2 ...`
        This method can create one.
        """
        return IntVar(slot=self.output_mgr.int_const(value), compiler=self)

    def add_scoreboard(self) -> str:
        """Apply for a new scoreboard"""
        return self.output_mgr.add_scoreboard()

    def allocate_entity_name(self) -> str:
        """Return a new entity name."""
        self._entity_max += 1
        return Config.entity_name + str(self._entity_max)

    def allocate_entity_tag(self) -> str:
        """Return a new entity tag."""
        self._entity_tag_max += 1
        return Config.entity_tag + str(self._entity_tag_max)

    def add_tmp_entity(self, entity: Union[TaggedEntity, EntityGroup]):
        self.current_generator.current_tmp_entities.append(entity)

    # -- End allocation --

    def find_module(self, meta: ModuleMeta) -> Union[str, None]:
        """Find a module.
        Return path of module or None is not found
        In details, this work like this:
        1. if leading_dots is 0, find the module in self.path
           else, find the module in the parent folder of
           self.main_dir; count of dots decides which parent folder
           e.g. main_dir at a/b/c; "...pack.file" -> a/pack
        2. when the start directory is decided, follow the names
           in `parents` and go deeper in folders
           e.g. main_dir at a/b/c; ".pack.sub.file" -> a/b/c/pack/sub
        3. find the module file in the directory
           e.g. main_dir at a/b/c; ".pack.file" -> a/b/c/pack/file.aca
        """
        ## Step 1
        if meta.leading_dots == 0:
            paths = self.path
        else:
            _path = self.main_dir
            for _ in range(meta.leading_dots - 1):
                _path = os.path.join(_path, os.pardir)
            paths = (_path,)
        ## Step 2~3
        for root in paths:
            ## Step 2
            final = os.path.join(root, *meta.parents)
            if not os.path.isdir(final):
                # failed to find any of the child directory,
                # meaning this `root` is invalid; continue
                continue
            ## Step 3
            for child in os.listdir(final):
                path = os.path.join(final, child)
                if not os.path.isfile(path):
                    continue
                got_name, ext = os.path.splitext(child)
                if (got_name == meta.last_name
                    and (ext == '.py' or ext == '.aca')):
                    return path
        return None

    def parse_module(self, meta: ModuleMeta) -> Tuple[AcaciaExpr, str]:
        """Parse and get a module and its path."""
        path = self.find_module(meta)
        if path is None:
            self.raise_error(
                Error(ErrorType.MODULE_NOT_FOUND, module=str(meta))
            )
        # Get the module accoding to path
        for p in self._cached_modules:
            # Return cached if exists
            if os.path.samefile(p, path):
                mod = self._cached_modules[p]
                break
        else:
            # Load the module
            _, ext = os.path.splitext(path)
            if ext == ".aca":
                # Parse the Acacia module
                with self._load_generator(path) as generator:
                    mod = generator.parse_as_module()
            elif ext == ".py":
                # Parse the binary module
                mod = BinaryModule(path, self)
            self._cached_modules[path] = mod
        return (mod, path)

    def get_module(self, meta: ModuleMeta):
        """Parse a module meta and just return the module
        An API for binary module developing.
        """
        return self.parse_module(meta)[0]

    @contextmanager
    def _load_generator(self, path: str):
        """Load the Generator of an Acacia source and store it at
        `self.current_generator`.
        """
        # Check if the module is being loading (prevent circular import)
        for p in self._loading_files:
            if os.path.samefile(p, path):
                self.raise_error(Error(ErrorType.CIRCULAR_PARSE, file_=path))
        src_file = self._open_file(path)
        oldf = self._current_file
        oldg = self.current_generator
        self._current_file = path
        self._loading_files.append(path)
        try:
            node = Parser(Tokenizer(src_file)).module()
            self.current_generator = Generator(
                node=node, main_file=self.file_main,
                compiler=self
            )
            yield self.current_generator
        except Error as err:
            if not err.file_set():
                err.set_file(path)
            raise err
        finally:
            src_file.close()
        self._current_file = oldf
        self.current_generator = oldg
        self._loading_files.pop()

    # --- I/O Util (Internal use) ---

    def _open_file(self, path: str):
        try:
            return open(path, 'r', **self.OPEN_ARGS)
        except Exception as err:
            self.raise_error(Error(ErrorType.IO, message=str(err)))

    def _read_file(self, path: str) -> str:
        """Read Acacia file and return source code."""
        x = self._open_file(path)
        try:
            with x:
                s = x.read()
        except Exception as err:
            self.raise_error(Error(ErrorType.IO, message=str(err)))
        else:
            return s

    def _write_file(self, content: str, path: str):
        """write `content` to `path`."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, 'w', **self.OPEN_ARGS) as f:
                f.write(content)
        except Exception as err:
            self.raise_error(Error(ErrorType.IO, message=str(err)))

    def _write_mcfunction(self, file: cmds.MCFunctionFile, path: str):
        """Write content of `file` to somewhere in output `path`
        e.g. when `path` is "a/b", `file.path` is "a", file is at
        "a/b/a.mcfunction".
        """
        self._write_file(
            content=file.to_str(),
            path=os.path.join(path, file.get_path() + '.mcfunction')
        )
