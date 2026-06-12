from typing import Protocol, TypeVar, runtime_checkable

from pysmt.fnode import FNode

T_Artifact = TypeVar("T_Artifact", covariant=True)


@runtime_checkable
class PropCompiler(Protocol[T_Artifact]):
    def compile(self, propositional_formula: FNode) -> T_Artifact: ...


@runtime_checkable
class QueryEngine(Protocol[T_Artifact]):
    def is_satisfiable(self) -> bool: ...

    def model_count(self) -> int: ...

    def entails(self, query_clause: FNode) -> bool: ...
