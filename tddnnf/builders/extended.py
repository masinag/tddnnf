from __future__ import annotations

from typing import Generic

from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import get_env

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import PropCompiler, T_Target


class TExtendedBuilder(Generic[T_Target]):
    """T-Extended compiler"""

    def __init__(self, compiler: PropCompiler[T_Target], env: Environment | None) -> None:
        self._env = env or get_env()
        self._compiler = compiler

    def build(
        self,
        phi: FNode,
        lemmas: list[FNode],
        abstractor: Abstractor,
    ) -> TheoryCompiledTarget[T_Target]:
        r"""Compile a T-Extended Target form of phi as
            sel.compiler($\phi \vee \bigvee \neg\ell$).

        Args:
            phi: SMT formula to compile.
            lemmas: Theory lemmas ruling out T-consistent truth assignments propositionally
                satisfying $\neg\phi$.
            abstractor: Maps SMT atoms to integer IDs.

        Returns:
            Compiled target bundled with the abstractor.
        """
        mgr = self._env.formula_manager
        negated = [mgr.Not(lem) for lem in lemmas]
        combined = mgr.Or(phi, *negated)
        artifact = self._compiler.compile(combined)
        return TheoryCompiledTarget(artifact, abstractor)
