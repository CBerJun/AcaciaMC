# The main Compiler of Acacia
# It assembles files and classes together and write output
from .constants import Config
from .error import *
from .tokenizer import Tokenizer
from .parser import Parser
from .mccmdgen.generator import *
from .mccmdgen.expression import *
from .mccmdgen.symbol import *

import os
from contextlib import contextmanager

__all__ = ['Compiler']

# --- COMPILER ---

class Compiler:
    # Start compiling the project
    # A Compiler manage the resources in the compile task and
    # connect the steps to compile: Tokenizer -> Parser -> Generator
    def __init__(self, main_path: str, open_args = {}):
        # main_path: path of main source file
        # open_args: args to pass to builtin `open`
        self.main_dir, _ = os.path.split(main_path)
        self.main_dir = os.path.realpath(self.main_dir)
        ACACIA = os.path.realpath(os.path.dirname(__file__))
        self.path = [
            os.path.join(ACACIA, 'modules'), # buitlin
            self.main_dir # find in program entry (main file)
        ] # modules will be found in these directories
        self.OPEN_ARGS = open_args
        self.file_init = MCFunctionFile('init') # initialize Acacia
        self.file_main = MCFunctionFile('load')
        self.file_tick = MCFunctionFile('tick') # runs every tick
        self.libs = [] # list of MCFunctionFiles, store the libraries
        # define `types` dict and generate builtin Types
        # keys:type subclasses of Type
        # values:Type instances of keys
        self.types = {}
        for cls in BUILTIN_TYPES:
            self.types[cls] = cls(compiler = self)
        # call `do_init` after creating all builtin instances
        for type_instance in self.types.values():
            type_instance.do_init()
        # define `call_result_classes` dict
        self.call_result_classes = BUILTIN_CALLRESULTS.copy()
        self.current_generator = None # the Generator that is running
        self._int_consts = {} # see method `add_int_const`
        self._lib_count = 0 # always equal to len(self.libs)
        # vars to record the resources that are applied
        self._score_max = 0 # max id of score allocated
        self._free_tmp_score = [] # free tmp scores (see method `allocate_tmp`)
        self._current_file = None # str; Path of current parsing file

        # --- START COMPILE ---
        ## comment on load.mcfunction
        self.file_main.write_debug(
            '## Usage: Run this Acacia project',
            '## Execute this before using interfaces!!!'
        )
        ## start
        with self._load_generator(main_path) as generator:
            generator.parse()

        # --- WRITE INIT ---
        self.file_init.write_debug(
            '## Usage: Initialize Acacia, only need to be ran ONCE',
            '## Execute this before running anything from Acacia!!!'
        )
        self.file_init.write_debug('# Register scoreboard')
        self.file_init.write(
            'scoreboard objectives add "%s" dummy' % Config.scoreboard
        )
        if self._int_consts:
            # only comment when there are constants used
            self.file_init.write_debug('# Load constants')
        for num, var in self._int_consts.items():
            self.file_init.write('scoreboard players set %s %d' % (var, num))
    
    def output(self, path: str):
        # output result to `path`
        # e.g. when `path` is "a/b", main file is
        # generated at "a/b/<Config.function_folder>/load.mcfunction"
        f_path = os.path.join(path, Config.function_folder)
        # --- CREATE FOLDERS ---
        for sub_path in (
            '', # the root folder
            'lib', # dependencies of main file
            'interface' # user defined interfaces
        ):
            target = os.path.join(f_path, sub_path)
            if not os.path.exists(target):
                os.mkdir(target)
        # --- WRITE FILES ---
        self._write_mcfunction(self.file_init, f_path)
        self._write_mcfunction(self.file_main, f_path)
        for file in self.libs:
            self._write_mcfunction(file, f_path)
        # --- tick.json AND tick.mcfunction ---
        if self.file_tick.has_content():
            self._write_mcfunction(self.file_tick, f_path)
            self._write_file(
                '{"values": ["tick"]}',
                os.path.join(path, 'tick.json')
            )
    
    def error(
        self, error_type: ErrorType, lineno = None, col = None, **kwargs
    ):
        # raise an error
        lineno = lineno if lineno is not None else \
            self.current_generator.processing_node.lineno
        col = col if col is not None else \
            self.current_generator.processing_node.col
        raise Error(
            error_type, lineno, col,
            file = self._current_file, **kwargs
        )
    
    def add_file(self, file: MCFunctionFile):
        # add a file to "libs" folder
        if not file.is_path_set():
            # if path of file is not given by Generator, we consider it
            # as a lib, and give it a id automatically
            self._lib_count += 1
            file.set_path('lib/acalib%d' % self._lib_count)
        self.libs.append(file)
    
    def add_type(self, type_: type):
        # type_:subclass of Type
        # add a user defined Type
        type_instance = type_(compiler = self)
        type_instance.do_init()
        self.types[type_] = type_instance
    
    def add_call_result(self, call_result: type, type_: type):
        # call_result:subclass of CallResult
        # type:subclass of Type
        # register a `call_result` class of `type_` type
        self.call_result_classes[type_] = call_result
    
    def get_call_result(self, type_: type):
        # get CallResult of `type_` type
        # type:subclass of Type
        if type_ in self.call_result_classes:
            return self.call_result_classes[type_]
        self.error(ErrorType.UNSUPPORTED_RESULT_TYPE, result_type = type_.name)
    
    # -- About allocation --
    
    def allocate(self) -> tuple:
        # apply for a brand new var
        # return (objective, selector)
        self._score_max += 1
        return (Config.scoreboard, 'acacia%d' % self._score_max)
    
    def allocate_tmp(self) -> tuple:
        # apply for a temporary score
        # NOTE only do this when you are really using a TEMPORARY var
        # because the var returned might have been used by others
        # NOTE tmp vars are only available within 1 statement
        # when it comes to next statement, current vars are deleted
        if self._free_tmp_score:
            # if there are free vars in list, reuse them
            res = self._free_tmp_score.pop()
        else:
            # else, allocate a new one
            res = self.allocate()
        self.current_generator.current_tmp_scores.append(res)
        return res
    
    def free_tmp(self, objective, selector):
        # free the tmp var allocated by method `allocate_tmp`
        self._free_tmp_score.append((objective, selector))

    def add_int_const(self, value: int) -> IntVar:
        # sometimes a constant is needed when calculating in MC
        # e.g. `a * 2`, we need a score to store 2, so that we can use
        # `scoreboard operation ... *= const2 ...`
        # this method applies one and return the var
        # the consts applied are in dict self._int_consts
        # where keys are ints, values are the vars applied
        
        # check if the int is already registered
        var = self._int_consts.get(value)
        if var is not None:
            return var
        # apply one and register
        var = self.types[BuiltinIntType].new_var()
        self._int_consts[value] = var
        return var
    
    def parse_module(self, path: str) -> AcaciaModule:
        # Add an Acacia module to compile project
        # `path` is the path of that module
        with self._load_generator(path) as generator:
            return generator.parse_as_module()
    
    # -- End allocation --
    
    def get_basic_scope(self) -> ScopedSymbolTable:
        # get the basic scope with builtin names
        res = ScopedSymbolTable()
        # builtin types
        for name, cls in (
            ('int', BuiltinIntType),
            ('bool', BuiltinBoolType)
        ):
            res.create(name, self.types[cls])
        return res

    def find_module(
        self, leading_dots: int, last_name: str, parents: list
    ) -> tuple:
        # find a module; the arguments are the same as ast.Import
        # return tuple(str<path of module>, ext<extension>)
        # In details, this work like this:
        # 1. if leading_dots is 0, find the module in self.path
        #    else, find the module in the parent folder of
        #    self.main_dir; count of dots decides which parent folder
        #    e.g. main_dir at a/b/c; "...pack.file" -> a/pack
        # 2. when the start directory is decided, follow the names
        #    in `parents` and go deeper in folders
        #    e.g. main_dir at a/b/c; ".pack.sub.file" -> a/b/c/pack/sub
        # 3. find the module file in the directory
        #    e.g. main_dir at a/b/c; ".pack.file" -> a/b/c/pack/file.aca
        ## Step 1
        if leading_dots == 0:
            paths = self.path
        else:
            _path = self.main_dir
            for _ in range(leading_dots - 1):
                _path = os.path.join(_path, os.pardir)
            paths = (_path,)
        ## Step 2~3
        for root in paths:
            ## Step 2
            final = os.path.join(root, *parents)
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
                if got_name == last_name and (ext == '.py' or ext == '.aca'):
                    return (path, ext)
        self.error(ErrorType.MODULE_NOT_FOUND, name = last_name)
    
    @contextmanager
    def _load_generator(self, path: str):
        # load the Generator of an Acacia source
        # and store it at self.current_generator
        src = self._read_file(path)
        oldf = self._current_file
        oldg = self.current_generator
        self._current_file = path
        self.current_generator = Generator(
            node = Parser(
                Tokenizer(src, path)
            ).module(),
            main_file = self.file_main,
            compiler = self
        )
        yield self.current_generator
        self._current_file = oldf
        self.current_generator = oldg
    
    # --- I/O Util (Internal use) ---

    def _read_file(self, path: str) -> str:
        # read Acacia file and return source code
        try:
            with open(path, 'r', **self.OPEN_ARGS) as f:
                return f.read()
        except Exception as err:
            self.error(ErrorType.IO, message = str(err))

    def _write_file(self, content: str, path: str):
        # write `content` to `path`
        try:
            with open(path, 'w', **self.OPEN_ARGS) as f:
                f.write(content)
        except Exception as err:
            self.error(ErrorType.IO, message = str(err))

    def _write_mcfunction(self, file: MCFunctionFile, path: str):
        # write content of `file` to somewhere in output `path`
        # e.g. when path is "a/b", file.path is "a",
        # file is at "a/b/a.mcfunction"
        self._write_file(
            content = file.to_str(),
            path = os.path.join(path, file.get_path() + '.mcfunction')
        )
