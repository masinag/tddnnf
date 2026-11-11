from __future__ import annotations

from collections.abc import Sequence
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
from tddnnf.core.persistence import read_metadata, saving_to, write_metadata
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
        with saving_to(directory) as temporary_directory:
            temporary_directory.mkdir()
            order = sorted(self.manager.vars, key=self.manager.level_of_var)
            self.manager.dump(str(temporary_directory / "circuit.dddmp"), [self.root])
            write_metadata(
                temporary_directory,
                "obdd",
                codec="dddmp-2.0",
                files=["circuit.dddmp"],
                var_count=len(order),
                variable_order=order,
            )

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
        directory = Path(directory)
        data = read_metadata(directory)
        order = data["variable_order"]
        manager = BDD()
        manager.configure(reordering=False)
        manager.declare(*order)
        (root,) = manager.load(str(directory / "circuit.dddmp"))
        return cls(root, manager)


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

    def compile(
        self,
        formula: FNode,
        abstractor: Abstractor,
        *,
        project_on: Sequence[FNode] | None = None,
        computation_logger: dict[str, object] | None = None,
    ) -> BddCompiledTarget:
        stats = StatsCollector(computation_logger)
        with stats.track_time("compile_time"):
            atoms = set(formula.get_atoms())
            if project_on is not None:
                atoms.update(project_on)
            atoms = list(atoms)
            assert all(atom in abstractor for atom in atoms), "Abstraction must be prepared before compilation"
            mgr = BDD()
            for i in sorted(abstractor.get_id(atom) for atom in atoms):
                mgr.declare(f"b{i}")
            walker = BddWalker(mgr, abstractor)
            root = walker.translate(formula)
            n_proj_vars: int
            if project_on is not None:
                project_set = set(project_on)
                forgotten = [f"b{abstractor.get_id(atom)}" for atom in atoms if atom not in project_set]
                if forgotten:
                    with stats.track_time("forget_time"):
                        root = root.exist(*forgotten)
                n_proj_vars = len(project_set)
            else:
                n_proj_vars = len(atoms)
            stats.log("n_atoms", len(atoms))
            stats.log("n_proj_vars", n_proj_vars)
            return BddCompiledTarget(root, mgr)
