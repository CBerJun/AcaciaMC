"""
The "post AST" pass happens after the parser pass and is responsible for
resolving imports and generating symbol tables.
"""

from typing import (
    Dict, List, Optional, NamedTuple, Set, Tuple, Union, Iterable,
    ValuesView, TYPE_CHECKING
)
from itertools import accumulate
from contextlib import contextmanager
import os

from acaciamc.tokenizer import Tokenizer
from acaciamc.parser import Parser
from acaciamc.diagnostic import DiagnosticError, Diagnostic
from acaciamc.utils.str_template import STStr
import acaciamc.ast as ast

if TYPE_CHECKING:
    from acaciamc.reader import Reader, FileEntry
    from acaciamc.diagnostic import DiagnosticsManager

class CachedModule(NamedTuple):
    """Represents a loaded and cached module."""

    ast: ast.Module
    file_entry: "FileEntry"
    namespace: "Scope"

class LoadingModule(NamedTuple):
    """Represents a module that is being loaded."""

    namespace: "Scope"

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
        self.processing: Dict[str, LoadingModule] = {}
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
        namespace = Scope(outer=None)
        self.processing[module_name] = LoadingModule(namespace)
        with file_entry.open() as file:
            tokenizer = Tokenizer(file, file_entry, self.diag_mgr,
                                  self.mc_version)
            parser = Parser(tokenizer)
            node = parser.module()
        PostASTVisitor(file_entry, namespace, self).visit(node)
        self.modules[module_name] = CachedModule(node, file_entry, namespace)
        del self.processing[module_name]

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

    def load_module(self, meta: ast.ModuleMeta) \
            -> Optional[Union[CachedModule, LoadingModule]]:
        """
        Toplevel function to load a module. Cache will be checked.
        All __init__.aca files required by the module, if any, will be
        loaded. Note that if a module partially loaded (due to circular
        import), then a `LoadingModule` is returned whose `namespace`
        may be incomplete. Return None if not found.
        """
        # Check cache
        normalized = meta.unparse()
        module = self.modules.get(normalized)
        if module is not None:
            return module
        module = self.processing.get(normalized)
        if module is not None:
            return module
        # Look for module
        lookup_result = self.find_module(meta)
        if lookup_result is None:
            return None
        # Process
        for package_name, init_entry in lookup_result.init_entries:
            self.process(init_entry, package_name)
        self.process(lookup_result.file_entry, normalized)
        return self.modules[normalized]

class Symbol:
    """
    Each definition of identifier generates a `Symbol`, and each
    `Identifier` node will be resolved to a `Symbol`.
    """

    def __init__(self, name: str, pos1: Tuple[int, int],
                 pos2: Tuple[int, int]):
        self.name = name
        self.pos1 = pos1
        self.pos2 = pos2

class Scope:
    """Container of `Symbol`s; represents a scope."""

    def __init__(self, outer: Optional["Scope"]):
        self.outer = outer
        # Mapping from all the names defined in this scope to their
        # corresponding symbols:
        self.names: Dict[str, Symbol] = {}
        # Keep track of unused names defined in this scope; used
        # for "unused-name" WARNING:
        self.unused_names: Set[str] = set()

    def add_symbol(self, name: str, symbol: Symbol) -> None:
        """Define a symbol in this scope."""
        self.names[name] = symbol
        self.unused_names.add(name)

    def mark_name_as_used(self, name: str) -> None:
        """
        Mark the given `name` as used. The name must be defined in this
        scope.
        """
        self.unused_names.discard(name)

    def lookup_symbol(self, name: str) -> Optional[Symbol]:
        """
        Lookup symbol in this scope as well as all the outer scopes,
        from inner to outer. If found, the `name` will be marked as
        "used" in the scope that defines it. Otherwise, return None.
        """
        scope = self
        while True:
            symbol = scope.names.get(name)
            if symbol is not None:
                scope.mark_name_as_used(name)
                return symbol
            if scope.outer is None:
                return None
            scope = scope.outer

class PostASTVisitor(ast.ASTVisitor):
    """
    Implements the "post AST" pass of compilation process.

    This class is intended to be used only by `ASTForest`, since this
    pass implements the import system which involves the tokenizing and
    parsing of other Acacia files, which is managed by `ASTForest`.

    This class puts `annotation`s on these AST nodes:
    * `Identifier`: A `Symbol` that this node references.
    * `ImportItem`: A `Symbol` that this import item imports.
    * `FromImportAll`: A `Dict[str, Tuple[Symbol, Symbol]]`. Each entry
      represents an item that gets imported. First `Symbol` is the
      symbol that gets defined in this file; second is the symbol that
      represents the imported item in the file that gets imported.
    * `IdentifierDef`: A `Optional[Symbol]`. Currently this is None iff
      it is the `name` child of an `ImportItem`. Otherwise, this node
      represents a definition of an identifier and its annotation will
      be the `Symbol` this defines.
    """

    def __init__(self, file_entry: "FileEntry", root_scope: Scope,
                 forest: ASTForest):
        self.file_entry = file_entry
        self.forest = forest
        self.scope: Scope = root_scope

    @contextmanager
    def new_scope(self):
        """
        Enter a new scope. Also warn on unused names on exit. Note that
        the toplevel scope (the root scope) is not created using this.
        That explains why unused names in global scope are not warned
        on.
        """
        original_scope = self.scope
        self.scope = Scope(self.scope)
        yield
        for name in self.scope.unused_names:
            symbol = self.scope.names[name]
            self.forest.diag_mgr.push_diagnostic(Diagnostic(
                "unused-name",
                self.file_entry.get_range(symbol.pos1, symbol.pos2),
                args={"name": STStr(name)}
            ))
        self.scope = original_scope

    def handle_id_def(self, id_def: ast.IdentifierDef):
        """
        Define a name in current scope using an `IdentifierDef` node.
        """
        id_def.annotation = \
            self.define_id(id_def.name, id_def.begin, id_def.end)

    def define_id(self, name: str, pos1: Tuple[int, int],
                  pos2: Tuple[int, int]) -> Symbol:
        """
        Define `name` in current scope with source range from `pos1` to
        `pos2`. Return the related `Symbol`.
        """
        # Do not use `lookup_symbol` since we do not want to search in
        # outer scopes; plus we do not want to mark the symbol as used:
        symbol = self.scope.names.get(name)
        if symbol is not None:
            # The name is already defined
            id_range = self.file_entry.get_range(pos1, pos2)
            err = DiagnosticError(Diagnostic(
                "name-redefinition", id_range,
                args={"name": STStr(name)}
            ))
            prev_id_range = self.file_entry.get_range(symbol.pos1, symbol.pos2)
            err.add_note(Diagnostic(
                "name-redefinition-note", prev_id_range, args={}
            ))
            raise err
        new_symbol = Symbol(name, pos1, pos2)
        self.scope.add_symbol(name, new_symbol)
        return new_symbol

    def handle_body(self, body: Iterable[ast.AST]):
        """Visit all nodes in `body` in a new scope."""
        with self.new_scope():
            for x in body:
                self.visit(x)

    def visit_ModuleMeta(self, node: ast.ModuleMeta):
        meta_range = self.file_entry.get_range(node.begin, node.end)
        imported_here = Diagnostic("imported-here", meta_range, args={})
        with self.forest.diag_mgr.using_note(imported_here):
            module = self.forest.load_module(node)
        if module is None:
            raise DiagnosticError(Diagnostic(
                "module-not-found", meta_range,
                args={"module": STStr(node.unparse())}
            ))
        return module

    # --- Nodes that use an identifier

    def visit_Identifier(self, node: ast.Identifier):
        # If we encounter an identifier, resolve it to a `Symbol` and
        # store the symbol in its `annotation`.
        symbol = self.scope.lookup_symbol(node.name)
        if symbol is None:
            id_range = self.file_entry.get_range(node.begin, node.end)
            raise DiagnosticError(Diagnostic(
                "undefined-name", id_range,
                args={"name": STStr(node.name)}
            ))
        node.annotation = symbol

    # --- Nodes that introduce a new scope

    def visit_If(self, node: ast.If):
        self.visit(node.condition)
        self.handle_body(node.body)
        self.handle_body(node.else_body)

    def visit_While(self, node: ast.While):
        self.visit(node.condition)
        self.handle_body(node.body)

    def visit_FuncData(self, node: ast.FuncData):
        self.child_visit(node.returns)
        with self.new_scope():
            params: ValuesView[ast.FormalParam] = node.params.values()
            for param in params:
                self.child_visit(param.type)
                self.child_visit(param.default)
            # Make sure parameter names are defined after parsing
            # the signature
            for param in params:
                self.handle_id_def(param.name)
            self.child_visit(node.body)

    def visit_InterfaceDef(self, node: ast.InterfaceDef):
        self.child_visit(node.path)
        self.handle_body(node.body)

    # --- Nodes that define a new name

    def visit_FuncDef(self, node: ast.FuncDef):
        self.visit(node.data)
        self.handle_id_def(node.name)

    def visit_EntityTemplateDef(self, node: ast.EntityTemplateDef):
        self.child_visit(node.parents)
        self.child_visit(node.new_method)
        self.child_visit(node.body)
        self.handle_id_def(node.name)

    def visit_VarDef(self, node: ast.VarDef):
        self.visit(node.type)
        self.child_visit(node.value)
        self.handle_id_def(node.target)

    def visit_AutoVarDef(self, node: ast.AutoVarDef):
        self.visit(node.value)
        self.handle_id_def(node.target)

    def visit_CompileTimeAssign(self, node: ast.CompileTimeAssign):
        self.child_visit(node.type)
        self.visit(node.value)
        self.handle_id_def(node.name)

    def visit_Import(self, node: ast.Import):
        self.visit(node.meta)
        self.handle_id_def(node.name)

    def visit_FromImport(self, node: ast.FromImport):
        # Use `visit_ModuleMeta` for better type hints
        module = self.visit_ModuleMeta(node.meta)
        for item in node.items:
            name: str = item.name.name
            symbol = module.namespace.lookup_symbol(name)
            if symbol is None:
                raise DiagnosticError(Diagnostic(
                    "cannot-import-name",
                    self.file_entry.get_range(item.name.begin, item.name.end),
                    args={"name": STStr(name),
                          "module": STStr(node.meta.unparse())}
                ))
            item.annotation = symbol
            self.handle_id_def(item.alias)

    def visit_FromImportAll(self, node: ast.FromImportAll):
        # Use `visit_ModuleMeta` for better type hints
        module = self.visit_ModuleMeta(node.meta)
        namespace = module.namespace
        # Toplevel namespace does not have outer
        assert namespace.outer is None
        node.annotation = {
            name: (
                # The symbol that is created (the alias) for this file:
                # Use the position of "*" (in "from x import *") as
                # source range of all the aliases:
                self.define_id(name, node.star_begin, node.star_end),
                # The symbol which defines the imported item in the file
                # that is imported:
                symbol
            )
            for name, symbol in namespace.names.items()
            # Do not import names starting with an underscore:
            if not name.startswith("_")
        }
        # Lastly, warn if the module that we import is partially
        # initialized
        if isinstance(module, LoadingModule):
            self.forest.diag_mgr.push_diagnostic(Diagnostic(
                "partial-wildcard-import",
                self.file_entry.get_range(node.begin, node.end),
                args={"module": STStr(node.meta.unparse())}
            ))

    def visit_For(self, node: ast.For):
        self.visit(node.expr)
        with self.new_scope():
            self.handle_id_def(node.name)
            self.child_visit(node.body)

    def visit_StructDef(self, node: ast.StructDef):
        self.child_visit(node.bases)
        self.handle_body(node.body)
        self.handle_id_def(node.name)
