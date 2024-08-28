"""Command abstraction optimizer."""

__all__ = ["Optimizer"]

from abc import ABCMeta, abstractmethod
from typing import Iterable, Dict, Set, List, Tuple

import acaciamc.mccmdgen.cmds as cmds
from acaciamc.mccmdgen.utils import unreachable


class Optimizer(cmds.FunctionsManager, metaclass=ABCMeta):
    def optimize(self):
        """Start optimizing."""
        self.opt_empty_functions()
        self.opt_dead_functions()
        self.opt_execute_as_ats()
        self.opt_function_inliner()

    @abstractmethod
    def entry_files(self) -> Iterable[cmds.MCFunctionFile]:
        """Must be implemented by subclasses to mark mcfunction files
        as an entry so that optimizer won't delete them even if they
        are not referenced.
        """
        pass

    def opt_dead_functions(self):
        """Remove unreferenced functions."""
        ref_map: Dict[cmds.MCFunctionFile, Set[cmds.MCFunctionFile]] = {}
        for file in self.files:
            refs = set(command.func_ref() for command in file.commands)
            if None in refs:
                refs.remove(None)
            ref_map[file] = refs
        visited = set()

        def _visit(file: cmds.MCFunctionFile):
            if file in visited:
                return
            visited.add(file)
            for ref in ref_map[file]:
                _visit(ref)

        for file in self.entry_files():
            _visit(file)
        self.files = list(visited)

    @property
    @abstractmethod
    def max_inline_file_size(self) -> int:
        pass

    def dont_inline_execute_call(self, file: cmds.MCFunctionFile) -> bool:
        """When True is returned, `execute ... run function` in `file`
        will not be inlined by `opt_function_inliner`.
        """
        return False

    def _resolve_execute(self, c: cmds.Command) \
            -> Tuple[List[cmds._ExecuteSubcmd], cmds.Command]:
        subcmds = []
        while isinstance(c, cmds.Execute):
            subcmds.extend(c.subcmds)
            c = c.runs
        return subcmds, c

    def opt_function_inliner(self):
        """Expand mcfunctions that only have 1 reference."""
        # Locating optimizable
        todo: Dict[cmds.MCFunctionFile,
        Tuple[cmds.MCFunctionFile, int, bool]] = {}
        called: Set[cmds.MCFunctionFile] = set()
        for file in self.files:
            allow_execute = not self.dont_inline_execute_call(file)
            for i, command in enumerate(file.commands):
                callee = command.func_ref()
                if callee is None:
                    continue
                if callee in called:
                    # More than 1 references
                    if callee in todo:
                        del todo[callee]
                    continue
                called.add(callee)
                subcmds, runs = self._resolve_execute(command)
                if not isinstance(runs, cmds.InvokeFunction):
                    # Not a direct /function call
                    continue
                passed_test = (
                        (not subcmds)
                        or (
                            # If there is /execute...
                            # Caller allows inlining calls with execute
                                allow_execute
                                # Environments other than if/unless may change
                                # during execution of commands, so we can't
                                # inline it.
                                and (all([
                            isinstance(
                                subcmd, (
                                    cmds.ExecuteScoreComp,
                                    cmds.ExecuteScoreMatch,
                                    cmds.ExecuteCond
                                )
                            )
                            for subcmd in subcmds
                        ]))
                        )
                )
                if passed_test or callee.cmd_length() == 1:
                    todo[callee] = (file, i, not passed_test)
        # Optimize
        # for callee, (caller, caller_index) in todo.items():
        #     print("Inlining %s, called by %s at %d" % (
        #         callee.get_path(), caller.get_path(), caller_index
        #     ))
        merged: Set[cmds.MCFunctionFile] = set()

        def _need_tmp(subcmds, commands: List[cmds.Command]) -> bool:
            slots = set()
            for subcmd in subcmds:
                if isinstance(subcmd, cmds.ExecuteCond):
                    return True
                if isinstance(subcmd, cmds.ExecuteScoreComp):
                    slots.add(subcmd.operand1)
                    slots.add(subcmd.operand2)
                elif isinstance(subcmd, cmds.ExecuteScoreMatch):
                    slots.add(subcmd.operand)
                else:
                    unreachable()
            for command in commands:
                for slot in slots:
                    if command.scb_did_assign(slot):
                        return True
            return False

        def _merge(caller: cmds.MCFunctionFile):
            if caller in merged:
                return
            merged.add(caller)
            tasks: List[Tuple[int, cmds.MCFunctionFile, bool]] = []
            for callee, (caller_got, caller_index, ensure_l1) in todo.items():
                if caller_got != caller:
                    continue
                _merge(callee)
                tasks.append((caller_index, callee, ensure_l1))
            tasks.sort(key=lambda x: x[0], reverse=True)
            for index, callee, ensure_len1 in tasks:
                subcmds, _ = self._resolve_execute(caller.commands[index])
                callee_len = callee.cmd_length()
                # Here `runs` must be /function that calls `callee`
                if subcmds and callee_len > self.max_inline_file_size:
                    # Prefixing every command in a long file with
                    # /execute condition can reduce performance,
                    # so we don't inline it.
                    continue
                if ensure_len1 and callee_len != 1:
                    continue
                # print("Merging %s to %s:%d" % (
                #     callee.get_path(), caller.get_path(), index
                # ))
                inserts = []
                # No need for tmp if callee has only 1 command
                if callee_len != 1 and _need_tmp(subcmds, callee.commands):
                    tmp = self.allocate()
                    inserts.append(cmds.ScbSetConst(tmp, 0))
                    inserts.append(cmds.Execute(
                        subcmds, cmds.ScbSetConst(tmp, 1)
                    ))
                    for command in callee.commands:
                        inserts.append(cmds.execute(
                            [cmds.ExecuteScoreMatch(tmp, "1")], command
                        ))
                elif subcmds:
                    for command in callee.commands:
                        inserts.append(cmds.execute(subcmds, command))
                else:
                    inserts.extend(callee.commands)
                fp = callee.get_path()
                inserts.insert(0, cmds.Comment(
                    "## Function call to %s inlined by optimizer" % fp
                ))
                inserts.append(cmds.Comment("## Inline of %s ended" % fp))
                caller.commands[index: index + 1] = inserts
                self.files.remove(callee)

        for caller, _, _ in todo.values():
            if caller not in todo:
                _merge(caller)

    def opt_execute_as_ats(self):
        """Remove "as @s" in /execute commands. """
        for file in self.files:
            for i, command in enumerate(file.commands):
                if isinstance(command, cmds.Execute):
                    for j, subcmd in enumerate(command.subcmds):
                        if (isinstance(subcmd, cmds.ExecuteEnv)
                                and subcmd.cmd == "as"
                                and subcmd.args == "@s"):
                            del command.subcmds[j]
                    if not command.subcmds:
                        # /execute with only a run subcommand can get
                        # rid of the /execute.
                        file.commands[i] = command.runs

    def opt_empty_functions(self):
        """Remove definition and invoke of empty functions."""
        removed = set()
        for i, file in reversed(tuple(enumerate(self.files))):
            if not file.has_content():
                removed.add(file)
                del self.files[i]
        for file in self.files:
            for i, command in enumerate(file.commands):
                ref = command.func_ref()
                if ref is not None and ref in removed:
                    file.commands[i] = cmds.Comment(
                        "## (Calling empty function) %s" % command.resolve()
                    )
