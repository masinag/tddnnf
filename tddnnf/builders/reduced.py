from __future__ import annotations

from typing import Generic

from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import get_env

from tddnnf.core.abstraction import AbstractionContext
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import PropCompiler, T_Target


class TReducedBuilder(Generic[T_Target]):
    """T-Reduced compiler"""

    def __init__(self, compiler: PropCompiler[T_Target], env: Environment | None) -> None:
        self._env = env or get_env()
        self._compiler = compiler

    def build(
        self,
        phi: FNode,
        lemmas: list[FNode],
        context: AbstractionContext,
    ) -> TheoryCompiledTarget[T_Target]:
        r"""Compile a T-Reduced Target form of phi as
            sel.compiler($\phi \wedge \bigwedge \ell$).

        Args:
            phi: SMT formula to compile.
            lemmas: Theory lemmas ruling out T-consistent truth assignments propositionally
                satisfying $\phi$.
            context: Maps SMT atoms to Boolean variables.

        Returns:
            Compiled target bundled with the abstraction context.
        """
        conjoined = self._env.formula_manager.And(phi, *lemmas)
        bool_formula = context.abstract(conjoined)
        artifact = self._compiler.compile(bool_formula)
        return TheoryCompiledTarget(artifact, context)
