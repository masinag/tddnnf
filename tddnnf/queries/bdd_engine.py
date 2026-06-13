from __future__ import annotations

from collections.abc import Iterator
from itertools import product

from pysmt.fnode import FNode

from tddnnf.compilers.cudd import BddCompiledTarget
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import QueryEngine
from tddnnf.core.pysmt_utils import clause_lits, cube_lits, is_clause, normalize_assumptions


class BddEngine(QueryEngine[BddCompiledTarget]):
    """Polynomial-time queries over a BDD compiled target."""

    def __init__(self, container: TheoryCompiledTarget[BddCompiledTarget]) -> None:
        self._target = container.target
        self._abstr = container.abstr

    def _restrict_chain(self, lits: list[FNode], negate: bool = False, root=None):
        assign: dict[str, bool] = {}
        for lit in lits:
            atom = lit.arg(0) if lit.is_not() else lit
            if atom not in self._abstr:
                raise ValueError(f"Atom {atom} is not known to the compiled target")
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

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        if not assumptions:
            n = self._abstr.var_count
            return int(self._target.root.count(n))
        unique = normalize_assumptions(assumptions)
        if unique is None:
            return 0
        restricted = self._restrict_chain(unique, negate=False)
        remaining = self._abstr.var_count - len(unique)
        return int(restricted.count(remaining))

    def is_valid(self) -> bool:
        return self._target.root == self._target.manager.true

    def entails_clause(self, query_clause: FNode) -> bool:
        if not is_clause(query_clause):
            raise ValueError(f"Expected a clause, got: {query_clause}")
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
        all_vars = [f"b{i}" for i in range(1, self._abstr.max_var + 1)]
        for partial in mgr.pick_iter(root):
            support = set(partial)
            unused = [v for v in all_vars if v not in support]
            if not unused:
                yield {self._abstr.get_atom(int(k[1:])): v for k, v in partial.items()}
            else:
                for bits in product([True, False], repeat=len(unused)):
                    full = dict(partial)
                    for var_name, val in zip(unused, bits):
                        full[var_name] = val
                    yield {self._abstr.get_atom(int(k[1:])): v for k, v in full.items()}
