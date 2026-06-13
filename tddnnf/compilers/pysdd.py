from __future__ import annotations

import json
from pathlib import Path
from typing import Self

import pysmt.operators as op
from pysdd.sdd import SddManager, SddNode
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import get_env
from pysmt.typing import BOOL
from pysmt.walkers import DagWalker, handles

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import PropCompiledTarget, PropCompiler


class SddCompiledTarget(PropCompiledTarget):
    """A propositionally compiled SDD target backed by PySDD."""

    def __init__(self, root: SddNode, manager: SddManager) -> None:
        self._root = root
        self._manager = manager

    @property
    def root(self) -> SddNode:
        return self._root

    @property
    def manager(self) -> SddManager:
        return self._manager

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        sdd_path = directory / "circuit.sdd"
        self._manager.save(str(sdd_path).encode(), self._root)
        metadata = {"var_count": self._manager.var_count()}
        (directory / "metadata.json").write_text(json.dumps(metadata))

    @classmethod
    def load(cls, directory: Path) -> Self:
        sdd_path = directory / "circuit.sdd"
        metadata = json.loads((directory / "metadata.json").read_text())
        var_count = metadata["var_count"]
        mgr = SddManager(var_count)
        root = mgr.read_sdd_file(str(sdd_path).encode())
        return cls(root, mgr)


class SddWalker(DagWalker):
    """Walks an SMT formula, building an SDD via recursive apply.

    Atom nodes (Bool symbols, theory relations) are mapped to
    SDD literals through an :class:`Abstractor`. Non-atom sub-expressions
    (theory operators, non-Bool symbols, numeric constants) are ignored.
    """

    def __init__(
        self,
        manager: SddManager,
        abstractor: Abstractor,
        env: Environment | None = None,
    ) -> None:
        DagWalker.__init__(self, env)
        self._mgr = manager
        self._abs = abstractor

    def walk_symbol(self, formula: FNode, args: tuple, **kwargs: object) -> SddNode | None:
        if not formula.is_symbol(BOOL):
            return None
        assert formula in self._abs, f"atom {formula} not pre-registered in abstractor"
        idx = self._abs.get_id(formula)
        return self._mgr.literal(idx)

    @handles(*op.CONSTANTS)
    def walk_constant(self, formula: FNode, args: tuple, **kwargs: object) -> SddNode | None:
        if not formula.is_bool_constant():
            return None
        return self._mgr.true() if formula.is_true() else self._mgr.false()

    @handles(*op.THEORY_OPERATORS)
    def walk_theory_op(self, formula: FNode, args: tuple, **kwargs: object) -> SddNode | None:
        return None

    @handles(*op.RELATIONS)
    def walk_theory_atom(self, formula: FNode, args: tuple, **kwargs: object) -> SddNode:
        assert formula in self._abs, f"atom {formula} not pre-registered in abstractor"
        idx = self._abs.get_id(formula)
        return self._mgr.literal(idx)

    def walk_not(self, formula: FNode, args: tuple, **kwargs: object) -> SddNode:
        return ~args[0]

    def walk_and(self, formula: FNode, args: tuple, **kwargs: object) -> SddNode:
        result = args[0]
        for arg in args[1:]:
            result = result & arg
        return result

    def walk_or(self, formula: FNode, args: tuple, **kwargs: object) -> SddNode:
        result = args[0]
        for arg in args[1:]:
            result = result | arg
        return result

    def walk_implies(self, formula: FNode, args: tuple, **kwargs: object) -> SddNode:
        return ~args[0] | args[1]

    def walk_iff(self, formula: FNode, args: tuple, **kwargs: object) -> SddNode:
        return (args[0] & args[1]) | (~args[0] & ~args[1])

    def walk_ite(self, formula: FNode, args: tuple, **kwargs: object) -> SddNode:
        return (args[0] & args[1]) | (~args[0] & args[2])

    def translate(self, formula: FNode) -> SddNode:
        result = self.walk(formula)
        assert result is not None, f"walk returned None for {formula}"
        return result


class SddCompiler(PropCompiler[SddCompiledTarget]):
    """PropCompiler that compiles an SMT formula into an SDD via PySDD.

    Accepts the original (non-abstracted) SMT formula. All atoms – both
    Bool symbols and theory atoms – are mapped to propositional variables
    through the provided :class:`Abstractor`.
    """

    def __init__(
        self,
        abstractor: Abstractor,
        env: Environment | None = None,
        vtree_type: str = "balanced",
    ) -> None:
        self._abstractor: Abstractor = abstractor
        self._env: Environment = env or get_env()
        self._vtree_type: str = vtree_type

    def compile(self, formula: FNode) -> SddCompiledTarget:
        for atom in formula.get_atoms():
            self._abstractor.get_id(atom)
        var_count = max(self._abstractor.max_var, 1)
        mgr = SddManager(var_count, self._vtree_type)
        mgr.auto_gc_and_minimize_on()
        walker = SddWalker(mgr, self._abstractor, self._env)
        root = walker.translate(formula)
        return SddCompiledTarget(root, mgr)
