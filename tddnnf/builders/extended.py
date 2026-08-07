from __future__ import annotations

from typing import Generic

from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import get_env

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import PropCompiler, T_Target
from tddnnf.core.stats_collector import StatsCollector


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
        self._stats = StatsCollector(computation_logger)

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
        with self._stats.track_time("build_time"):
            mgr = self._env.formula_manager
            negated = [mgr.Not(lem) for lem in lemmas]
            combined = mgr.Or(phi, *negated)
            artifact = self._compiler.compile(combined, project_on=project_on)
            if project_on is not None:
                projection_atoms = project_on
            else:
                projection_atoms = sorted(combined.get_atoms(), key=lambda a: abstractor.get_id(a))
        self._stats.log("n_lemmas", len(lemmas))
        self._stats.log("n_projection_atoms", len(projection_atoms))
        return TheoryCompiledTarget(artifact, abstractor, projection_atoms=projection_atoms)
