from __future__ import annotations

from pathlib import Path
from typing import Protocol, Self, TypeVar, runtime_checkable

from pysmt.fnode import FNode


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

    def compile(self, formula: FNode) -> T_Target_co: ...


@runtime_checkable
class QueryEngine(Protocol[T_Target_co]):
    """Polynomial-time queries over a compiled target."""

    def is_satisfiable(self) -> bool: ...

    def model_count(self) -> int: ...

    def entails(self, query_clause: FNode) -> bool: ...
