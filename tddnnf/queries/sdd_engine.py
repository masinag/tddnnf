from __future__ import annotations

from collections.abc import Iterator

from pysmt.fnode import FNode

from tddnnf.compilers.pysdd import SddCompiledTarget, SddWalker
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import QueryEngine
from tddnnf.core.pysmt_utils import is_clause, is_cube


class SddEngine(QueryEngine[SddCompiledTarget]):
    """Polynomial-time queries over an SDD compiled target."""

    def __init__(self, container: TheoryCompiledTarget[SddCompiledTarget]) -> None:
        self._target = container.target
        self._abstr = container.abstr
        self._walker = SddWalker(self._target.manager, self._abstr)

    def is_satisfiable(self) -> bool:
        return not self._target.root.is_false()

    def count_truth_assignments(self) -> int:
        return self._target.root.model_count()

    def is_valid(self) -> bool:
        return self._target.root.is_true()

    def clause_entails(self, query_clause: FNode) -> bool:
        if not is_clause(query_clause):
            raise ValueError(f"Expected a clause, got: {query_clause}")
        query_sdd = self._walker.translate(query_clause)
        return (self._target.root & ~query_sdd).is_false()

    def is_implicant(self, query_cube: FNode) -> bool:
        if not is_cube(query_cube):
            raise ValueError(f"Expected a cube, got: {query_cube}")
        query_sdd = self._walker.translate(query_cube)
        return (query_sdd & ~self._target.root).is_false()

    def enumerate_truth_assignments(self) -> Iterator[dict[FNode, bool]]:
        if self._target.root.is_false():
            return
        for assignment in self._target.root.models():
            yield {self._abstr.get_atom(var_id): val == 1 for var_id, val in assignment.items()}
