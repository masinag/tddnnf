from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, Self, TypeVar, runtime_checkable

from pysmt.fnode import FNode

if TYPE_CHECKING:
    from tddnnf.core.abstraction import Abstractor
    from tddnnf.core.containers import TheoryCompiledTarget


@runtime_checkable
class PropCompiledTarget(Protocol):
    """A propositionally compiled target (d-DNNF, SDD, OBDD, ...)."""

    def save(self, directory: Path) -> None: ...

    @classmethod
    def load(cls, directory: Path) -> Self: ...


T_Target = TypeVar("T_Target", bound=PropCompiledTarget)
T_Target_co = TypeVar("T_Target_co", bound=PropCompiledTarget, covariant=True)


@runtime_checkable
class PropCompiler(Protocol[T_Target_co]):
    """Compiles a propositional formula into a PropCompiledTarget."""

    def __init__(self, abstractor: Abstractor) -> None: ...

    def compile(self, formula: FNode) -> T_Target_co: ...


@runtime_checkable
class QueryEngine(Protocol[T_Target_co]):
    """Polynomial-time queries over a compiled target."""

    def __init__(self, target: TheoryCompiledTarget[T_Target_co]) -> None: ...

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

    def entails_clause(self, query_clause: FNode) -> bool:
        """True iff the compiled formula entails the given clause."""
        ...

    def is_implicant(self, query_cube: FNode) -> bool:
        """True iff the given cube is an implicant of the compiled formula."""
        ...

    def enumerate_truth_assignments(self) -> Iterator[dict[FNode, bool]]:
        """Enumerate all total truth assignments satisfying the compiled formula.

        Each assignment maps every atom known to the compiled target to True or False.
        """
        ...
