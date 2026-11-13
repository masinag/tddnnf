from __future__ import annotations

from collections.abc import Generator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, Self, TypeVar, runtime_checkable

from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

if TYPE_CHECKING:
    from tddnnf.core.abstraction import Abstractor
    from tddnnf.core.theory_compiled_target import TheoryCompiledTarget


@dataclass(frozen=True)
class DagSize:
    """DAG size as reachable vertices and child-reference edges."""

    vertices: int
    edges: int


@runtime_checkable
class PropCompiledTarget(Protocol):
    """A propositionally compiled target (d-DNNF, SDD, OBDD, ...)."""

    def dag_size(self) -> DagSize: ...

    def save(self, directory: Path) -> None: ...

    @classmethod
    def load(cls, directory: Path) -> Self:
        """Load an artifact, validating its metadata schema before reading payloads."""
        ...

    def to_pysmt(self, abstr: Abstractor, mgr: FormulaManager) -> FNode:
        """Reconstruct the formula from the compiled DAG."""
        ...


T_Target = TypeVar("T_Target", bound=PropCompiledTarget)
T_Target_co = TypeVar("T_Target_co", bound=PropCompiledTarget, covariant=True)


@runtime_checkable
class PropCompiler(Protocol[T_Target_co]):
    """Compile existentially or universally quantified formula over a complete declared vocabulary.

    Retained variables follow all_atoms order. Formula atoms must be declared;
    quantifier sets must be subsets with only one kind nonempty, and all atoms
    must be pre-registered.
    """

    def compile(
        self,
        formula: FNode,
        abstractor: Abstractor,
        *,
        all_atoms: Sequence[FNode],
        exists_atoms: Sequence[FNode] = (),
        forall_atoms: Sequence[FNode] = (),
        computation_logger: dict[str, object] | None = None,
    ) -> T_Target_co: ...


# QuerySession normalizes queries; engines expect literals aligned to the target projection.
@runtime_checkable
class QueryEngine(Protocol[T_Target_co]):
    """Polynomial-time queries over a compiled target using flat, aligned literal lists."""

    def __init__(self, container: TheoryCompiledTarget[T_Target_co]) -> None: ...

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
