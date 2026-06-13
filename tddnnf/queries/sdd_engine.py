from __future__ import annotations

from collections.abc import Iterator

from pysmt.fnode import FNode

from tddnnf.compilers.pysdd import SddCompiledTarget
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import QueryEngine
from tddnnf.core.pysmt_utils import clause_lits, cube_lits, is_clause


class SddEngine(QueryEngine[SddCompiledTarget]):
    """Polynomial-time queries over an SDD compiled target."""

    def __init__(self, container: TheoryCompiledTarget[SddCompiledTarget]) -> None:
        self._target = container.target
        self._abstr = container.abstr

    def _lit_to_sdd(self, lit: FNode):
        atom = lit.arg(0) if lit.is_not() else lit
        var_id = self._abstr.get_id(atom)
        node = self._target.manager.literal(var_id)
        return ~node if lit.is_not() else node

    def is_satisfiable(self) -> bool:
        return not self._target.root.is_false()

    def _condition_chain(self, lits: list[FNode], negate: bool = False):
        temp = self._target.root
        for lit in lits:
            sdd_lit = self._lit_to_sdd(lit)
            if negate:
                sdd_lit = ~sdd_lit
            temp = temp.condition(sdd_lit)
            if temp.is_false():
                break
        return temp

    def count_truth_assignments(self, cube: FNode | None = None) -> int:
        if cube is None:
            return self._target.root.global_model_count()
        lits = cube_lits(cube)
        if lits is None:
            return 0
        temp = self._condition_chain(lits, negate=False)
        # condition doesn't remove vars from manager count; shift corrects overcount by 2^k
        return temp.global_model_count() >> len(lits)

    def is_valid(self) -> bool:
        return self._target.root.is_true()

    def clause_entails(self, query_clause: FNode) -> bool:
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
        return self._condition_chain(lits, negate=False).is_true()

    def enumerate_truth_assignments(self) -> Iterator[dict[FNode, bool]]:
        if self._target.root.is_false():
            return
        for assignment in self._target.root.models():
            yield {self._abstr.get_atom(var_id): val == 1 for var_id, val in assignment.items()}
