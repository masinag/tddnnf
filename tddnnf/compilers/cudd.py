from __future__ import annotations

import json
from pathlib import Path
from typing import Self

import pysmt.operators as op
from dd.cudd import BDD, Function
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.typing import BOOL
from pysmt.walkers import DagWalker, handles

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import DagSize, PropCompiledTarget, PropCompiler
from tddnnf.core.stats_collector import StatsCollector


class BddCompiledTarget(PropCompiledTarget):
    """A propositionally compiled OBDD target backed by CUDD."""

    def __init__(self, root: Function, manager: BDD) -> None:
        self._root = root
        self._manager = manager

    @property
    def root(self) -> Function:
        return self._root

    @property
    def manager(self) -> BDD:
        return self._manager

    def dag_size(self) -> DagSize:
        seen: set[int] = set()
        edges = 0
        stack = [self._root]

        while stack:
            node = stack.pop()
            node_key = int(node)
            if node_key in seen:
                continue
            seen.add(node_key)
            if node.var is None:
                continue
            edges += 2
            stack.append(node.high)
            stack.append(node.low)

        return DagSize(vertices=int(self._root.dag_size), edges=edges)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        bdd_path = directory / "circuit.dddmp"
        self._manager.dump(str(bdd_path), [self._root])
        var_count = len(self._manager.vars)
        (directory / "metadata.json").write_text(json.dumps({"var_count": var_count}))

    def to_pysmt(self, abstr: Abstractor, mgr: FormulaManager) -> FNode:
        _memo: dict[Function, FNode] = {}

        def convert(f: Function) -> FNode:
            if f in _memo:
                return _memo[f]
            if f.var is None:
                result: FNode = mgr.TRUE() if not f.negated else mgr.FALSE()
            else:
                idx = int(f.var[1:])
                atom = abstr.get_atom(idx)
                high = convert(f.high)
                low = convert(f.low)
                result = mgr.Or(mgr.And(atom, high), mgr.And(mgr.Not(atom), low))
                if f.negated:
                    result = mgr.Not(result)
            _memo[f] = result
            return result

        return convert(self._root)

    @classmethod
    def load(cls, directory: Path) -> Self:
        bdd_path = directory / "circuit.dddmp"
        metadata = json.loads((directory / "metadata.json").read_text())
        var_count = metadata["var_count"]
        mgr = BDD()
        for i in range(1, var_count + 1):
            mgr.declare(f"b{i}")
        roots = mgr.load(str(bdd_path))
        return cls(roots[0], mgr)


class BddWalker(DagWalker):
    """Walks an SMT formula, building a BDD via recursive apply.

    Atom nodes (Bool symbols, theory relations) are mapped to
    BDD variables through an :class:`Abstractor`. Non-atom sub-expressions
    (theory operators, non-Bool symbols, numeric constants) are ignored.
    """

    def __init__(self, manager: BDD, abstractor: Abstractor) -> None:
        DagWalker.__init__(self)
        self._mgr = manager
        self._abs = abstractor

    def walk_symbol(self, formula: FNode, args: tuple, **kwargs: object) -> Function | None:
        if not formula.is_symbol(BOOL):
            return None
        assert formula in self._abs, f"atom {formula} not pre-registered in abstractor"
        idx = self._abs.get_id(formula)
        return self._mgr.var(f"b{idx}")

    @handles(*op.CONSTANTS)
    def walk_constant(self, formula: FNode, args: tuple, **kwargs: object) -> Function | None:
        if not formula.is_bool_constant():
            return None
        return self._mgr.true if formula.is_true() else self._mgr.false

    @handles(*op.THEORY_OPERATORS)
    def walk_theory_op(self, formula: FNode, args: tuple, **kwargs: object) -> None:
        return None

    @handles(*op.RELATIONS)
    def walk_theory_atom(self, formula: FNode, args: tuple, **kwargs: object) -> Function:
        assert formula in self._abs, f"atom {formula} not pre-registered in abstractor"
        idx = self._abs.get_id(formula)
        return self._mgr.var(f"b{idx}")

    def walk_not(self, formula: FNode, args: tuple, **kwargs: object) -> Function:
        return ~args[0]

    def walk_and(self, formula: FNode, args: tuple, **kwargs: object) -> Function:
        result = args[0]
        for arg in args[1:]:
            result = result & arg
        return result

    def walk_or(self, formula: FNode, args: tuple, **kwargs: object) -> Function:
        result = args[0]
        for arg in args[1:]:
            result = result | arg
        return result

    def walk_implies(self, formula: FNode, args: tuple, **kwargs: object) -> Function:
        return ~args[0] | args[1]

    def walk_iff(self, formula: FNode, args: tuple, **kwargs: object) -> Function:
        return (args[0] & args[1]) | (~args[0] & ~args[1])

    def walk_ite(self, formula: FNode, args: tuple, **kwargs: object) -> Function:
        return (args[0] & args[1]) | (~args[0] & args[2])

    def translate(self, formula: FNode) -> Function:
        result = self.walk(formula)
        assert result is not None, f"walk returned None for {formula}"
        return result


class BddCompiler(PropCompiler[BddCompiledTarget]):
    """PropCompiler that compiles an SMT formula into a BDD via CUDD.

    Accepts the original (non-abstracted) SMT formula. All atoms -- both
    Bool symbols and theory atoms -- are mapped to propositional variables
    through the provided :class:`Abstractor`.
    """

    def __init__(self, abstractor: Abstractor, computation_logger: dict[str, object] | None = None) -> None:
        self._abstractor: Abstractor = abstractor
        self._stats = StatsCollector(computation_logger)

    def compile(self, formula: FNode, project_on: list[FNode] | None = None) -> BddCompiledTarget:
        with self._stats.track_time("compile_time"):
            atoms = set(formula.get_atoms())
            if project_on is not None:
                atoms.update(project_on)
            atoms = list(atoms)
            for atom in atoms:
                self._abstractor.get_id(atom)
            max_var = max(self._abstractor.max_var, 1)
            mgr = BDD()
            for i in range(1, max_var + 1):
                mgr.declare(f"b{i}")
            walker = BddWalker(mgr, self._abstractor)
            root = walker.translate(formula)
            n_proj_vars: int
            if project_on is not None:
                project_set = set(project_on)
                forgotten = [f"b{self._abstractor.get_id(atom)}" for atom in atoms if atom not in project_set]
                if forgotten:
                    with self._stats.track_time("forget_time"):
                        root = root.exist(*forgotten)
                n_proj_vars = len(project_set)
            else:
                n_proj_vars = len(atoms)
            self._stats.log("n_atoms", len(atoms))
            self._stats.log("n_proj_vars", n_proj_vars)
            return BddCompiledTarget(root, mgr)
