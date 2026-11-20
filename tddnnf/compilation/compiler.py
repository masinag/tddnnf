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
        """Compile the Boolean abstraction of `formula` into a target in the `T_Target_co` propositional language.

        If `exists_atoms` is not empty, the formula to be compiled is `exists W. phi`, where `W` is `exists_atoms`.
        If `forall_atoms` is not empty, the formula to be compiled is `forall W. phi`, where `W` is `forall_atoms`.
        `exists_atoms` and `forall_atoms` cannot both be non-empty.

        Args:
            phi: The formula to compile.
            abstractor: Mapping from formula atoms to integer ids, identifying the variables in the compiled formula.
            all_atoms: Superset of all atoms occurring in the formula.
            exists_atoms: Atoms to existentially quantify during compilation.
            forall_atoms: Atoms to universally quantify during compilation.
            computation_logger: Dictionary where to store compilation statistics.

        Returns:
            T_Target_co: The compiled target.
        """
        ...
