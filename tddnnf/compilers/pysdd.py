from __future__ import annotations

from array import array
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Self

import pysmt.operators as op
from pysdd.sdd import SddManager, SddNode, Vtree
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.typing import BOOL
from pysmt.walkers import DagWalker, handles

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import DagSize, PropCompiledTarget, PropCompiler
from tddnnf.core.persistence import read_metadata, saving_to, write_metadata
from tddnnf.core.stats_collector import StatsCollector


class SddCompiledTarget(PropCompiledTarget):
    """A propositionally compiled SDD target backed by PySDD."""

    def __init__(self, root: SddNode, manager: SddManager, remapping: Mapping[int, int]) -> None:
        self._remapping = MappingProxyType(dict(remapping))
        self._root = root
        self._manager = manager

    @property
    def remapping(self) -> Mapping[int, int]:
        return self._remapping

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
        inverse = {native: abstraction for abstraction, native in self.remapping.items()}

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
                atom = abstr.get_atom(inverse[idx])
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
        with saving_to(directory) as temporary_directory:
            temporary_directory.mkdir()
            self.manager.save(str(temporary_directory / "circuit.sdd").encode(), self.root)
            self.manager.vtree().save(str(temporary_directory / "circuit.vtree").encode())
            write_metadata(
                temporary_directory,
                "sdd",
                codec="pysdd",
                files=["circuit.sdd", "circuit.vtree"],
                var_count=self.manager.var_count(),
                remapping={str(k): v for k, v in self.remapping.items()},
            )

    @classmethod
    def load(cls, directory: Path) -> Self:
        directory = Path(directory)
        data = read_metadata(directory)
        remapping = {int(k): v for k, v in data["remapping"].items()}
        vtree_path = directory / "circuit.vtree"
        if not vtree_path.is_file():
            raise FileNotFoundError(vtree_path)
        tree = Vtree.from_file(str(vtree_path).encode())
        manager = SddManager.from_vtree(tree)
        manager.auto_gc_and_minimize_off()
        root = manager.read_sdd_file(str(directory / "circuit.sdd").encode())
        return cls(root, manager, remapping)


class SddWalker(DagWalker):
    """Walks an SMT formula, building an SDD via recursive apply.

    Atom nodes (Bool symbols, theory relations) are mapped to
    SDD literals through an :class:`Abstractor`. Non-atom sub-expressions
    (theory operators, non-Bool symbols, numeric constants) are ignored.
    """

    def __init__(self, manager: SddManager, abstractor: Abstractor, remapping: Mapping[int, int]) -> None:
        DagWalker.__init__(self)
        self._mgr = manager
        self._abs = abstractor
        self._remapping = remapping

    def walk_symbol(self, formula: FNode, args: tuple, **kwargs: object) -> SddNode | None:
        if not formula.is_symbol(BOOL):
            return None
        assert formula in self._abs, f"atom {formula} not pre-registered in abstractor"
        idx = self._abs.get_id(formula)
        return self._mgr.literal(self._remapping[idx])

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
        return self._mgr.literal(self._remapping[idx])

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

    def __init__(self, vtree_type: str = "balanced", auto_gc_and_minimize: bool = True) -> None:
        """Configure the native vtree and joint automatic GC/minimization setting.

        Args:
            vtree_type: One of "right", "left", "vertical", "balanced", "random".
            auto_gc_and_minimize: Boolean enabling both native automatic garbage
                collection and minimization (default True). Types are trusted
                as annotated.

        Raises:
            ValueError: If the vtree name is unsupported by the native library.
        """
        if vtree_type not in ("right", "left", "vertical", "balanced", "random"):
            raise ValueError(f"Unsupported vtree_type: {vtree_type!r}")
        self._vtree_type = vtree_type
        self._auto_gc_and_minimize = auto_gc_and_minimize

    def compile(
        self,
        formula: FNode,
        abstractor: Abstractor,
        *,
        project_on: Sequence[FNode] | None = None,
        computation_logger: dict[str, object] | None = None,
    ) -> SddCompiledTarget:
        stats = StatsCollector(computation_logger)
        with stats.track_time("compile_time"):
            atoms = set(formula.get_atoms())
            if project_on is not None:
                atoms.update(project_on)
            atoms = list(atoms)
            assert all(atom in abstractor for atom in atoms), "Abstraction must be prepared before compilation"
            ids = sorted(abstractor.get_id(atom) for atom in atoms)
            remapping = {idx: native for native, idx in enumerate(ids, 1)}
            var_count = max(len(ids), 1)
            vtree = Vtree(var_count=var_count, vtree_type=self._vtree_type)
            mgr = SddManager.from_vtree(vtree)
            if self._auto_gc_and_minimize:
                mgr.auto_gc_and_minimize_on()
            else:
                mgr.auto_gc_and_minimize_off()
            walker = SddWalker(mgr, abstractor, remapping)
            root = walker.translate(formula)
            n_proj_vars: int
            if project_on is not None:
                project_set = set(project_on)
                exists_map = array("i", [0]) * (mgr.var_count() + 1)
                for atom in atoms:
                    if atom not in project_set:
                        vid = abstractor.get_id(atom)
                        exists_map[remapping[vid]] = 1
                with stats.track_time("forget_time"):
                    root = mgr.exists_multiple(exists_map, root)
                n_proj_vars = len(project_set)
            else:
                n_proj_vars = len(atoms)
            stats.log("n_atoms", len(atoms))
            stats.log("n_proj_vars", n_proj_vars)
            return SddCompiledTarget(root, mgr, remapping)
