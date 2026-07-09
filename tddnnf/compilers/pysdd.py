from __future__ import annotations

import json
from array import array
from pathlib import Path
from typing import Self

import pysmt.operators as op
from pysdd.sdd import SddManager, SddNode
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.typing import BOOL
from pysmt.walkers import DagWalker, handles

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import DagSize, PropCompiledTarget, PropCompiler
from tddnnf.core.stats_collector import StatsCollector


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

    def dag_size(self) -> DagSize:
        seen: set[int] = set()
        edges = 0
        stack = [self._root]

        while stack:
            node = stack.pop()
            node_id = node.id
            if node_id in seen:
                continue
            seen.add(node_id)
            if node.is_decision():
                for prime, sub in node.elements():
                    edges += 2
                    stack.append(prime)
                    stack.append(sub)

        return DagSize(vertices=int(self._root.size()), edges=edges)

    def to_pysmt(self, abstr: Abstractor, mgr: FormulaManager) -> FNode:
        memo: dict[int, FNode] = {}

        def convert(node: SddNode) -> FNode:
            nid = node.id
            cached = memo.get(nid)
            if cached is not None:
                return cached
            if node.is_true():
                result = mgr.TRUE()
            elif node.is_false():
                result = mgr.FALSE()
            elif node.is_literal():
                lit = node.literal
                idx = abs(lit)
                atom = abstr.get_atom(idx)
                result = atom if lit > 0 else mgr.Not(atom)
            else:
                terms: list[FNode] = []
                for prime, sub in node.elements():
                    terms.append(mgr.And(convert(prime), convert(sub)))
                result = mgr.Or(terms)
            memo[nid] = result
            return result

        return convert(self._root)

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

    def __init__(self, manager: SddManager, abstractor: Abstractor) -> None:
        DagWalker.__init__(self)
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
        vtree_type: str = "balanced",
        computation_logger: dict[str, object] | None = None,
    ) -> None:
        self._abstractor: Abstractor = abstractor
        self._vtree_type: str = vtree_type
        self._stats = StatsCollector(computation_logger)

    def compile(self, formula: FNode, project_on: list[FNode] | None = None) -> SddCompiledTarget:
        with self._stats.track_time("compile_time"):
            atoms = set(formula.get_atoms())
            if project_on is not None:
                atoms.update(project_on)
            atoms = list(atoms)
            for atom in atoms:
                self._abstractor.get_id(atom)
            var_count = max(self._abstractor.max_var, 1)
            mgr = SddManager(var_count, self._vtree_type)
            mgr.auto_gc_and_minimize_on()
            walker = SddWalker(mgr, self._abstractor)
            root = walker.translate(formula)
            n_proj_vars: int
            if project_on is not None:
                project_set = set(project_on)
                exists_map = array("i", [0]) * (mgr.var_count() + 1)
                for atom in atoms:
                    if atom not in project_set:
                        vid = self._abstractor.get_id(atom)
                        exists_map[vid] = 1
                with self._stats.track_time("forget_time"):
                    root = mgr.exists_multiple(exists_map, root)
                n_proj_vars = len(project_set)
            else:
                n_proj_vars = len(atoms)
            self._stats.log("n_atoms", len(atoms))
            self._stats.log("n_proj_vars", n_proj_vars)
            return SddCompiledTarget(root, mgr)
