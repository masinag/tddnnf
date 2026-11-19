from __future__ import annotations

from collections.abc import Generator
from typing import Protocol, runtime_checkable

from pysmt.fnode import FNode

from tddnnf.compilation.targets import T_Target_co, TheoryCompiledTarget


@runtime_checkable
class QueryEngine(Protocol[T_Target_co]):
    """Interface to a Boolean NNF reasoner."""

    def __init__(self, theory_target: TheoryCompiledTarget[T_Target_co]) -> None: ...

    def close(self) -> None:
        """Release engine resources; repeated calls are safe. Defaults to no-op."""

    def is_satisfiable(self, assumptions: list[FNode] | None = None) -> bool:
        """True iff the compiled formula has a satisfying assignment.

        If *assumptions* is given, each literal is fixed to True before
        checking satisfiability.
        """
        ...

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        """Number of total truth assignments satisfying the compiled formula.

        If *assumptions* is given, count only assignments that also satisfy
        every literal in the list.
        """
        ...

    def is_valid(self) -> bool:
        """True iff the compiled formula is valid (true under all assignments)."""
        ...

    def entails_clause(self, query_clause: list[FNode]) -> bool:
        """True iff the compiled formula entails the given clause."""
        ...

    def is_implicant(self, query_cube: list[FNode]) -> bool:
        """True iff the given cube is an implicant of the compiled formula."""
        ...

    def enumerate_truth_assignments(self) -> Generator[dict[FNode, bool], None, None]:
        """Enumerate all total truth assignments satisfying the compiled formula.

        Each call returns an independent, closable generator. Assignments map every
        projection atom to True or False, in projection order.
        """
        ...
