"""
The main compiler of Acacia.
It assembles files and classes together and writes output.
"""

__all__ = ['Compiler', 'Config']

from typing import (
    Tuple, Union, Optional, Callable, Dict, NamedTuple, TYPE_CHECKING
)
import os
from contextlib import contextmanager

from acaciamc.ast import ModuleMeta
from acaciamc.error import *
from acaciamc.tokenizer import Tokenizer
from acaciamc.parser import Parser
from acaciamc.mccmdgen.generator import Generator
from acaciamc.mccmdgen.expression import *
from acaciamc.mccmdgen.symbol import SymbolTable
from acaciamc.mccmdgen.optimizer import Optimizer
import acaciamc.mccmdgen.cmds as cmds

if TYPE_CHECKING:
    from acaciamc.tools.versionlib import VERSION_T

class OutputManager(cmds.FunctionsManager):
    def __init__(self, cfg: "Config"):
        super().__init__(cfg.scoreboard)
        self._cfg = cfg
        self._lib_count = 0
        sep = '' if not cfg.root_folder else "/"
        self._mcfp_template = f"{cfg.root_folder}{sep}%s"
        self.tick_file_path = f"{self._cfg.internal_folder}/tick"
        self.tick_file_full_path = self.mcfunction_path(self.tick_file_path)

    def mcfunction_path(self, path: str) -> str:
        return self._mcfp_template % path

    def new_file(self, file: cmds.MCFunctionFile, path: str):
        file.set_path(self.mcfunction_path(path))
        self.add_file(file)

    def add_lib(self, file: cmds.MCFunctionFile):
        self._lib_count += 1
        fname = f"{self._cfg.internal_folder}/acalib{self._lib_count}"
        self.new_file(file, fname)

class OutputOptimized(OutputManager, Optimizer):
    def entry_files(self):
        internal = self.mcfunction_path(self._cfg.internal_folder) + "/"
        for file in self.files:
            path = file.get_path()
            if (
                not path.startswith(internal)
                or path == self.tick_file_full_path
            ):
                yield file

    @property
    def max_inline_file_size(self) -> int:
        return self._cfg.max_inline_file_size

    def dont_inline_execute_call(self, file: cmds.MCFunctionFile) -> bool:
        # Expanding /execute function calls in tick.mcfunction can
        # decrease performance badly.
        return file.get_path() == self.tick_file_full_path

class Config(NamedTuple):
    # Generate debug comments in .mcfunction files
    debug_comments: bool = False
    # Subpath of "functions" in a behavior pack where Acacia would put
    # all mcfunctions into. Must be a sequence of Acacia identifiers
    # joined with "/", or an empty string. Redundant slashes are NOT
    # allowed.
    root_folder: str = ''
    # Name of the folder that contains internal mcfunctions
    internal_folder: str = '_acacia'
    # Name of mcfunction file that executes the program
    main_file: str = 'main'
    # Prefix of scoreboard that Acacia uses to hold data
    scoreboard: str = 'acacia'
    # Default type of entity spawned)
    entity_type: str = 'armor_stand'
    # Default position to spawn entity
    entity_pos: str = '~ ~ ~'
    # Prefix of entity tags
    entity_tag: str = 'acacia'
    # Minecraft version
    mc_version: "VERSION_T" = (1, 20, 20)
    # Minecraft Education Edition features
    education_edition: bool = False
    # Split initialization commands from main file
    split_init: bool = False
    # Name of init file (ignored if split_init is False)
    init_file: str = 'init'
    # Enable optimizer
    optimizer: bool = True
    # Maximum lines of commands an mcfunction can have to be inlined
    # even if it is called with /execute condition (ignored if optimizer
    # is False)
    max_inline_file_size: int = 20
    # Encoding of input and output files
    encoding: Optional[str] = None

class Compiler:
    """Start compiling the project
    A Compiler manage the resources in the compile task and
    connect the steps to compile: Tokenizer -> Parser -> Generator.
    """
    def __init__(self, main_path: str, cfg: Optional[Config] = None):
        """
        main_path: path of main source file
        cfg: optional `Config` object
        """
        self.main_dir, _ = os.path.split(main_path)
        self.main_dir = os.path.realpath(self.main_dir)
        ACACIA = os.path.realpath(os.path.dirname(__file__))
        self.path = [
            os.path.join(ACACIA, 'modules'),  # buitlin modules
            self.main_dir  # find in program entry (main file)
        ]  # modules will be found in these directories
        self.cfg = Config() if cfg is None else cfg
        if self.cfg.optimizer:
            self.output_mgr = OutputOptimized(self.cfg)
        else:
            self.output_mgr = OutputManager(self.cfg)
        self.file_main = cmds.MCFunctionFile()  # load program
        self.file_tick = cmds.MCFunctionFile()  # runs every tick
        self.output_mgr.new_file(self.file_main, self.cfg.main_file)
        self.output_mgr.new_file(
            self.file_tick, self.output_mgr.tick_file_path
        )
        self.current_generator = None  # the Generator that is running
        # vars to record the resources that are applied
        self._interface_paths: Dict[str, SourceLocation] = {}
        self._score_max = 0  # max id of score allocated
        self._scoreboard_max = 0  # max id of scoreboard allocated
        self._entity_tag_max = 0  # max id of entity tag allocated
        self._free_tmp_score = []  # free tmp scores (see `allocate_tmp`)
        self._current_file = None  # str; Path of current parsing file
        self._cached_modules = {}  # loaded modules are cached here
        self._loading_files = []  # paths of Acacia modules that are loading
        self._before_finish_cbs = []  # callbacks to run before finish

        # --- BUILTINS ---
        self.base_template = EntityTemplate(
            name="Entity",
            field_types={}, field_metas={}, methods={},
            method_qualifiers={}, parents=[], metas={}, compiler=self
        )
        self.external_template = EntityTemplate(
            "ExternalEntity",
            field_types={}, field_metas={}, methods={},
            method_qualifiers={}, parents=[], metas={}, compiler=self
        )
        self.builtins = SymbolTable.from_other(
            self.get_module(ModuleMeta("builtins")).attribute_table
        )

        # --- START COMPILE ---
        ## start
        with self._load_generator(main_path) as generator:
            generator.parse()
        ## callback
        for cb in self._before_finish_cbs:
            cb()
        ## init
        init = self.output_mgr.generate_init()
        if self.cfg.split_init:
            init_file = cmds.MCFunctionFile()
            self.output_mgr.new_file(init_file, self.cfg.init_file)
            init_file.write_debug(
                '## Usage: Initialize Acacia, only need to be ran ONCE',
                '## Execute this before running anything from Acacia!!!'
            )
            init_file.extend(init)
        else:
            self.file_main.commands[:0] = init
        ## comment on main.mcfunction
        self.file_main.commands[:0] = [
            cmds.Comment('## Usage: Run this Acacia project'),
            cmds.Comment('## Execute this before using interfaces!!!')
        ]
        ## optimize
        if isinstance(self.output_mgr, OutputOptimized):
            self.output_mgr.optimize()

    def output(self, path: str):
        """
        Output result to `path`.
        e.g. when `path` is "a/b", main file is generated at
        "a/b/{self.cfg.root_folder}/main.mcfunction".
        """
        # Mcfunctions
        for file in self.output_mgr.files:
            self._write_mcfunction(file, path)
        # tick.json
        if self.file_tick.has_content():
            self._write_file(
                '{"values": ["%s"]}' % self.output_mgr.tick_file_full_path,
                os.path.join(path, 'tick.json')
            )

    def raise_error(self, error: Error):
        if self.current_generator is not None:
            self.current_generator.fix_error_location(error)
        error.location.file = self._current_file
        raise error

    def add_file(self, file: cmds.MCFunctionFile, path: Optional[str] = None):
        """
        Add a new file to the project.
        `path` is the path relative to the self.cfg.root_folder.
        If `path` is None, the file will be added as an internal lib.
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

    def allocate_entity_tag(self) -> str:
        """Return a new entity tag."""
        self._entity_tag_max += 1
        return self.cfg.entity_tag + str(self._entity_tag_max)

    # -- End allocation --

    def before_finish(self, callback: Callable[[], None]):
        """Add a callback before compilation finishes."""
        self._before_finish_cbs.append(callback)

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

    def lookup_interface(self, path: str) -> Optional[SourceLocation]:
        """Return the location of the interface if it exists."""
        path = path.lower()
        if path in self._interface_paths:
            return self._interface_paths[path]
        return None

    def add_interface(self, path: str, location: SourceLocation):
        """Register an interface."""
        path = path.lower()
        self._interface_paths[path] = location

    def is_reserved_path(self, path: str) -> bool:
        """Return if a mcfunction path is reserved (not for user)."""
        checks = [self.cfg.main_file, self.cfg.internal_folder]
        if self.cfg.split_init:
            checks.append(self.cfg.init_file)
        path = path.lower()
        for check in checks:
            check = check.lower()
            if path == check or path.startswith(check + "/"):
                return True
        return False

    def swap_exprs(self, x: VarValue, y: VarValue) -> CMDLIST_T:
        """Swap two `VarValue`s that are assignable to each other."""
        try:
            res = x.swap(y)
        except NotImplementedError:
            # Fall back
            tmp = x.data_type.new_var()
            res = [
                *x.export(tmp),
                *y.export(x),
                *tmp.export(y)
            ]
        return res

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
            node = Parser(Tokenizer(src_file, self.cfg.mc_version)).module()
        except Error as err:
            if not err.location.file_set():
                err.location.file = path
            raise
        finally:
            src_file.close()
        self.current_generator = Generator(
            node=node, main_file=self.file_main,
            file_name=path, compiler=self
        )
        yield self.current_generator
        self._current_file = oldf
        self.current_generator = oldg
        self._loading_files.pop()

    # --- I/O Util (Internal use) ---

    def _open_file(self, path: str):
        try:
            return open(path, 'r', encoding=self.cfg.encoding)
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
        """Write `content` to `path`."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, 'w', encoding=self.cfg.encoding) as f:
                f.write(content)
        except Exception as err:
            self.raise_error(Error(ErrorType.IO, message=str(err)))

    def _write_mcfunction(self, file: cmds.MCFunctionFile, path: str):
        """Write content of `file` to somewhere in output `path`
        e.g. when `path` is "a/b", `file.path` is "a", file is at
        "a/b/a.mcfunction".
        """
        self._write_file(
            content=file.to_str(debugging=self.cfg.debug_comments),
            path=os.path.join(path, file.get_path() + '.mcfunction')
        )
