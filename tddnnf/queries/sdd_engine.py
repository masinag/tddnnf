from __future__ import annotations

from pysmt.fnode import FNode

from tddnnf.compilers.pysdd import SddCompiledTarget, SddWalker
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import QueryEngine
from tddnnf.core.pysmt_utils import is_clause


class SddEngine(QueryEngine[SddCompiledTarget]):
    """Polynomial-time queries over an SDD compiled target."""

    def __init__(self, container: TheoryCompiledTarget[SddCompiledTarget]) -> None:
        self._target = container.target
        self._context = container.context
        self._walker = SddWalker(self._target.manager, self._context)

    def is_satisfiable(self) -> bool:
        return not self._target.root.is_false()

    def model_count(self) -> int:
        return self._target.root.model_count()

    def clause_entails(self, query_clause: FNode) -> bool:
        if not is_clause(query_clause):
            raise ValueError(f"Expected a clause, got: {query_clause}")
        query_sdd = self._walker.translate(query_clause)
        return (self._target.root & ~query_sdd).is_false()
