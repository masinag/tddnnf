from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Generic

from pysmt.fnode import FNode

from tddnnf.core.interfaces import QueryEngine, T_Target

if TYPE_CHECKING:
    from tddnnf.context import QueryContext


class NormalizingQueryEngine(QueryEngine[T_Target], Generic[T_Target]):
    """Align query inputs before delegating to a backend query engine."""

    def __init__(self, inner: QueryEngine[T_Target], context: QueryContext) -> None:
        self._inner = inner
        self._context = context

    def is_satisfiable(self, assumptions: list[FNode] | None = None) -> bool:
        """Align assumptions and delegate satisfiability checking."""
        return self._inner.is_satisfiable(self._context.align_assumptions(assumptions))

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        """Align assumptions and delegate truth-assignment counting."""
        return self._inner.count_truth_assignments(self._context.align_assumptions(assumptions))

    def is_valid(self) -> bool:
        """Delegate validity checking unchanged."""
        return self._inner.is_valid()

    def entails_clause(self, query_clause: FNode) -> bool:
        """Align a clause and delegate entailment checking."""
        return self._inner.entails_clause(self._context.align_formula(query_clause))

    def is_implicant(self, query_cube: FNode) -> bool:
        """Align a cube and delegate implicant checking."""
        return self._inner.is_implicant(self._context.align_formula(query_cube))

    def enumerate_truth_assignments(self) -> Iterator[dict[FNode, bool]]:
        """Delegate truth-assignment enumeration unchanged."""
        return self._inner.enumerate_truth_assignments()
