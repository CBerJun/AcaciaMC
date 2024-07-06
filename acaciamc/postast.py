"""
The "post AST" pass happens after the parser pass and is responsible for
resolving imports and generating symbol tables.
"""

from typing import Dict, List, Optional, NamedTuple, Set, Tuple, TYPE_CHECKING
from itertools import accumulate
import os

from acaciamc.tokenizer import Tokenizer
from acaciamc.parser import Parser
from acaciamc.diagnostic import DiagnosticError, Diagnostic, error_note
from acaciamc.utils.str_template import STStr
import acaciamc.ast as ast

if TYPE_CHECKING:
    from acaciamc.reader import Reader, FileEntry
    from acaciamc.diagnostic import DiagnosticsManager

class CachedModule(NamedTuple):
    """Represents a loaded and cached module."""

    ast: ast.Module
    file_entry: "FileEntry"

class ModuleLookupResult(NamedTuple):
    """Returned by `ASTForest.find_module()`."""

    # The module itself:
    file_entry: "FileEntry"
    # All the __init__.aca files needed by this module, from the
    # top most one to the inner most one closest to the module.
    # Each element is in the form (module normalized name, file entry)
    init_entries: Tuple[Tuple[str, "FileEntry"], ...]

class ASTForest:
    """
    Manages the "frontend" of the whole compilation process.
    Stores all the AST trees in this compilation.
    """

    def __init__(self, reader: "Reader", diag_mgr: "DiagnosticsManager",
                 main_file: "FileEntry", mc_version: Tuple[int, ...]):
        """
        When constructed, the given `main_file` will be immediately
        parsed. The results are in `self.modules`, which stores the
        annotated AST of all the modules loaded. The main file's AST is
        accessible as the "__main__" module. `self.succeeded` tells if
        the compilation succeeded (i.e. no ERROR diagnostic occured).
        """
        self.reader = reader
        self.diag_mgr = diag_mgr
        self.mc_version = mc_version
        self.modules: Dict[str, CachedModule] = {}
        self.processing: Set[str] = set()
        # Configure module lookup path
        self.path: List[str] = []
        if main_file.file_name is not None:
            self.path.append(os.path.dirname(main_file.file_name))
        # XXX is there a better way to figure out the standard library
        # path that does not rely on relative file path?
        acacia_package = os.path.dirname(os.path.realpath(__file__))
        self.path.append(os.path.join(acacia_package, "modules"))
        # Start parsing the main file
        with self.diag_mgr.capture_errors():
            self.process(main_file, "__main__")
        # If `process` failed to add "__main__" to `self.modules` then
        # we know that an error has occured.
        self.succeeded = "__main__" in self.modules

    def process(self, file_entry: "FileEntry", module_name: str) -> None:
        """
        Convert a `file` into an AST. The AST will be cached by its
        normalized `module_name` in `self.modules`.
        """
        if module_name in self.processing:
            return
        self.processing.add(module_name)
        with file_entry.open() as file:
            tokenizer = Tokenizer(file, file_entry, self.diag_mgr,
                                  self.mc_version)
            parser = Parser(tokenizer)
            node = parser.module()
        PostASTVisitor(file_entry, self).visit(node)
        self.modules[module_name] = CachedModule(node, file_entry)
        self.processing.remove(module_name)

    def get_package_init(self, path: str) -> str:
        """Get path to the entry file of a package."""
        return os.path.join(path, "__init__.aca")

    def is_package(self, path: str) -> bool:
        """Return if a path represents an Acacia package."""
        if not (os.path.exists(path) and os.path.isdir(path)):
            return False
        init_path = self.get_package_init(path)
        if not (os.path.exists(init_path) and os.path.isfile(init_path)):
            return False
        return True

    def find_module(self, meta: ast.ModuleMeta) \
            -> Optional[ModuleLookupResult]:
        """
        Look for the source file for given module `meta`. If not found,
        return None, otherwise a `ModuleLookupResult` is returned.
        """
        init_files: List[str] = []
        packages = meta.path[:-1]
        last_name = meta.path[-1]
        for path in self.path:
            for package in packages:
                path = os.path.join(path, package)
                if not self.is_package(path):
                    break
                init_files.append(self.get_package_init(path))
            else:
                module_path = os.path.join(path, f"{last_name}.aca")
                result = None
                if os.path.exists(module_path) and os.path.isfile(module_path):
                    result = module_path
                else:
                    package_path = os.path.join(path, last_name)
                    if self.is_package(package_path):
                        result = self.get_package_init(package_path)
                if result is not None:
                    module_entry = self.reader.get_real_file(result)
                    init_entries = map(self.reader.get_real_file, init_files)
                    package_names = accumulate(
                        packages, lambda a, b: f"{a}.{b}"
                    )
                    return ModuleLookupResult(
                        module_entry,
                        tuple(zip(package_names, init_entries))
                    )
        return None

    def load_module(self, meta: ast.ModuleMeta) -> bool:
        """
        Toplevel function to load a module. Cache will be checked.
        All __init__.aca files required by the module, if any, will be
        loaded. Return whether the module was successfully found.
        """
        # Check cache
        normalized = meta.unparse()
        if normalized in self.processing or normalized in self.modules:
            return True
        # Look for module
        lookup_result = self.find_module(meta)
        if lookup_result is None:
            return False
        # Process
        for package_name, init_entry in lookup_result.init_entries:
            self.process(init_entry, package_name)
        self.process(lookup_result.file_entry, normalized)
        return True

class PostASTVisitor(ast.ASTVisitor):
    """
    Implements the "post AST" pass of compilation process.

    This class is intended to be used only by `ASTForest`, since this
    pass implements the import system which involves the tokenizing and
    parsing of other Acacia files, which is managed by `ASTForest`.
    """

    def __init__(self, file_entry: "FileEntry", forest: ASTForest):
        self.file_entry = file_entry
        self.forest = forest

    def visit_ModuleMeta(self, node: ast.ModuleMeta):
        meta_range = self.file_entry.get_range(node.begin, node.end)
        imported_here = Diagnostic("imported-here", meta_range, args={})
        with self.forest.diag_mgr.using_note(imported_here):
            found = self.forest.load_module(node)
        if not found:
            raise DiagnosticError(Diagnostic(
                "module-not-found", meta_range,
                args={"module": STStr(node.unparse())}
            ))
