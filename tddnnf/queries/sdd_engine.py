from __future__ import annotations

from collections.abc import Iterator

from pysmt.fnode import FNode

from tddnnf.compilers.pysdd import SddCompiledTarget
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import QueryEngine
from tddnnf.core.pysmt_utils import clause_lits, cube_lits, is_clause, normalize_assumptions


class SddEngine(QueryEngine[SddCompiledTarget]):
    """Polynomial-time queries over an SDD compiled target."""

    def __init__(self, container: TheoryCompiledTarget[SddCompiledTarget]) -> None:
        self._target = container.target
        self._abstr = container.abstr

    def _lit_to_sdd(self, lit: FNode):
        atom = lit.arg(0) if lit.is_not() else lit
        if atom not in self._abstr:
            raise ValueError(f"Atom {atom} is not known to the compiled target")
        var_id = self._abstr.get_id(atom)
        node = self._target.manager.literal(var_id)
        return ~node if lit.is_not() else node

    def _condition_chain(self, lits: list[FNode], negate: bool = False, root=None):
        temp = self._target.root if root is None else root
        for lit in lits:
            sdd_lit = self._lit_to_sdd(lit)
            if negate:
                sdd_lit = ~sdd_lit
            temp = temp.condition(sdd_lit)
            if temp.is_false():
                break
        return temp

    def is_satisfiable(self, assumptions: list[FNode] | None = None) -> bool:
        if not assumptions:
            return not self._target.root.is_false()
        return not self._condition_chain(assumptions, negate=False).is_false()

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        if not assumptions:
            return self._target.root.global_model_count()
        unique = normalize_assumptions(assumptions)
        if unique is None:
            return 0
        temp = self._condition_chain(unique, negate=False)
        return temp.global_model_count() >> len(unique)

    def is_valid(self) -> bool:
        return self._target.root.is_true()

    def entails_clause(self, query_clause: FNode) -> bool:
        if not is_clause(query_clause):
            raise ValueError(f"Expected a clause, got: {query_clause}")
        lits = clause_lits(query_clause)
        if lits is None:
            return True
        return self._condition_chain(lits, negate=True).is_false()

    def is_implicant(self, query_cube: FNode) -> bool:
        lits = cube_lits(query_cube)
        if lits is None:
            return True
        return self._condition_chain(lits).is_true()

    def enumerate_truth_assignments(self) -> Iterator[dict[FNode, bool]]:
        root = self._target.root
        if root.is_false():
            return
        for assignment in root.models():
            yield {self._abstr.get_atom(var_id): val == 1 for var_id, val in assignment.items()}
