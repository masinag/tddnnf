from __future__ import annotations

from typing import Generic

from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import get_env

from tddnnf.context import TheoryCompilation
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import PropCompiler, T_Target


class TExtendedBuilder(Generic[T_Target]):
    """T-Extended compiler"""

    def __init__(
        self,
        compiler: PropCompiler[T_Target],
        env: Environment | None = None,
        computation_logger: dict[str, object] | None = None,
    ) -> None:
        self._env = env or get_env()
        self._compiler = compiler
        self._computation_logger = computation_logger

    def build(
        self,
        phi: FNode,
        lemmas: list[FNode],
        abstractor: Abstractor,
        project_on: list[FNode] | None = None,
    ) -> TheoryCompiledTarget[T_Target]:
        r"""Compile a T-Extended Target form of phi as
            sel.compiler($\phi \vee \bigvee \neg\ell$).

        Args:
            phi: SMT formula to compile.
            lemmas: Theory lemmas ruling out T-consistent truth assignments propositionally
                satisfying $\neg\phi$.
            abstractor: Maps SMT atoms to integer IDs.
            project_on: Keep only these atoms in the compiled target;
                all others are existentially quantified away.

        Returns:
            Compiled target bundled with the abstractor.
        """
        with TheoryCompilation(phi, project_on=project_on, env=self._env) as compilation:
            return compilation._compile(self._compiler, lemmas, True, self._computation_logger, abstractor)
