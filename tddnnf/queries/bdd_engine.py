from __future__ import annotations

from collections.abc import Iterator
from itertools import product

from pysmt.fnode import FNode

from tddnnf.compilers.cudd import BddCompiledTarget
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import QueryEngine
from tddnnf.core.pysmt_utils import clause_lits, cube_lits, normalize_assumptions


class BddEngine(QueryEngine[BddCompiledTarget]):
    """Polynomial-time queries over a BDD compiled target."""

    def __init__(self, container: TheoryCompiledTarget[BddCompiledTarget]) -> None:
        self._target = container.target
        self._abstr = container.abstr
        self._care_vars: list[FNode] = container.care_vars
        self._care_set: set[FNode] = set(container.care_vars)

    def _restrict_chain(self, lits: list[FNode], negate: bool = False, root=None):
        assign: dict[str, bool] = {}
        for lit in lits:
            atom = lit.arg(0) if lit.is_not() else lit
            if atom not in self._care_set:
                raise ValueError(f"Atom {atom} is not a care variable")
            val = (not lit.is_not()) if not negate else lit.is_not()
            name = f"b{self._abstr.get_id(atom)}"
            if name in assign and assign[name] != val:
                return self._target.manager.false
            assign[name] = val
        source = self._target.root if root is None else root
        if not assign:
            return source
        mgr = self._target.manager
        return mgr.let(assign, source)

    def is_satisfiable(self, assumptions: list[FNode] | None = None) -> bool:
        if not assumptions:
            return self._target.root != self._target.manager.false
        mgr = self._target.manager
        return self._restrict_chain(assumptions, negate=False) != mgr.false

    def _forgotten_var_count(self) -> int:
        return len(self._target.manager.vars) - len(self._care_vars)

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        n = len(self._target.manager.vars)
        forgotten = self._forgotten_var_count()
        if not assumptions:
            total = self._target.root.count(n)
            return int(total) >> forgotten
        unique = normalize_assumptions(assumptions)
        if unique is None:
            return 0
        restricted = self._restrict_chain(unique, negate=False)
        total = restricted.count(n)
        return int(total) >> (forgotten + len(unique))

    def is_valid(self) -> bool:
        return self._target.root == self._target.manager.true

    def entails_clause(self, query_clause: FNode) -> bool:
        lits = clause_lits(query_clause)
        if lits is None:
            return True
        mgr = self._target.manager
        return self._restrict_chain(lits, negate=True) == mgr.false

    def is_implicant(self, query_cube: FNode) -> bool:
        lits = cube_lits(query_cube)
        if lits is None:
            return True
        mgr = self._target.manager
        return self._restrict_chain(lits) == mgr.true

    def enumerate_truth_assignments(self) -> Iterator[dict[FNode, bool]]:
        root = self._target.root
        if root == self._target.manager.false:
            return
        mgr = self._target.manager
        care_names = [f"b{self._abstr.get_id(a)}" for a in self._care_vars]
        for partial in mgr.pick_iter(root):
            support = set(partial)
            unused = [v for v in care_names if v not in support]
            if not unused:
                yield {self._abstr.get_atom(int(k[1:])): v for k, v in partial.items()}
            else:
                for bits in product([True, False], repeat=len(unused)):
                    full = dict(partial)
                    for var_name, val in zip(unused, bits):
                        full[var_name] = val
                    yield {self._abstr.get_atom(int(k[1:])): v for k, v in full.items()}
