from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pysmt.fnode import FNode

from tddnnf.compilation.targets import T_Target_co
from tddnnf.core.abstraction import Abstractor


@runtime_checkable
class PropCompiler(Protocol[T_Target_co]):
    """Interface to a Boolean NNF Compiler."""

    def compile(
        self,
        phi: FNode,
        abstractor: Abstractor,
        *,
        all_atoms: Sequence[FNode],
        exists_atoms: Sequence[FNode] = (),
        forall_atoms: Sequence[FNode] = (),
        computation_logger: dict[str, object] | None = None,
    ) -> T_Target_co:
        """Compile the Boolean abstraction of `formula` into the `T_Target_co` propositional language.

        If `exists_atoms` is not empty, the formula to be compiled is `exists W. phi`, where `W` is `exists_atoms`.
        If `forall_atoms` is not empty, the formula to be compiled is `forall W. phi`, where `W` is `forall_atoms`.
        `exists_atoms` and `forall_atoms` cannot both be non-empty.

        Args:
            phi: the formula to compile.
            abstractor: mapping from formula atoms to integer ids, identifying the variables in the compiled formula.
            all_atoms: superset of all atoms occurring in the formula.
            exists_atoms: atoms to existentially quantify during compilation.
            forall_atoms: atoms to universally quantify during compilation.
            computation_logger: a dictionary where to store compilation statistics.

        Returns:
            The compiled formula.
        """
        ...
