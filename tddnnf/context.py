from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Self

from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import get_env

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import PropCompiler, T_Target
from tddnnf.core.pysmt_utils import is_atom
from tddnnf.core.stats_collector import StatsCollector
from tddnnf.normalization.normalizer import NormalizerWalker


class TheoryCompilation:
    """Normalize inputs and compile either theory construction through one pipeline.

    Callers must provide Boolean FNodes for phi and lemmas, with all input DAGs
    (including projection entries) belonging to the selected environment.
    These type and environment preconditions are not checked at runtime.
    """

    def __init__(
        self,
        phi: FNode,
        project_on: Sequence[FNode] | None = None,
        env: Environment | None = None,
    ) -> None:
        self._env = env if env is not None else get_env()
        self._closed = False
        self._normalizer = None
        try:
            self._normalizer = NormalizerWalker(self._env)
            self.phi = self.normalize(phi)
            atoms = sorted(self.phi.get_atoms(), key=FNode.node_id) if project_on is None else project_on
            self.project_on = tuple(
                dict.fromkeys(normalized for atom in atoms if (normalized := self._normalize_atom(atom)) is not None)
            )
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> Self:
        self._ensure_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Release normalization resources; safe to call repeatedly."""
        self._closed = True
        if self._normalizer is not None:
            self._normalizer.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Compilation session is closed")

    def normalize(self, formula: FNode) -> FNode:
        """Normalize a Boolean FNode supplied in this session's environment."""
        self._ensure_open()
        assert self._normalizer is not None
        return self._normalizer.normalize(formula)

    def compile_treduced(
        self,
        compiler: PropCompiler[T_Target],
        lemmas: Iterable[FNode],
        computation_logger: dict[str, object] | None = None,
        *,
        abstractor: Abstractor | None = None,
    ) -> TheoryCompiledTarget[T_Target]:
        """Conjoin theory lemmas enumerated over normalized phi."""
        return self._compile(compiler, lemmas, False, computation_logger, abstractor)

    def compile_textended(
        self,
        compiler: PropCompiler[T_Target],
        lemmas: Iterable[FNode],
        computation_logger: dict[str, object] | None = None,
        *,
        abstractor: Abstractor | None = None,
    ) -> TheoryCompiledTarget[T_Target]:
        """Disjoin negated theory lemmas enumerated over Not(phi)."""
        return self._compile(compiler, lemmas, True, computation_logger, abstractor)

    def _compile(
        self,
        compiler: PropCompiler[T_Target],
        lemmas: Iterable[FNode],
        extended: bool,
        computation_logger: dict[str, object] | None = None,
        abstractor: Abstractor | None = None,
    ) -> TheoryCompiledTarget[T_Target]:
        self._ensure_open()
        if isinstance(compiler, (str, type)) or not isinstance(compiler, PropCompiler):
            raise TypeError("Expected a configured compiler instance")
        normalized_lemmas = [self.normalize(lemma) for lemma in lemmas]
        stats = StatsCollector(computation_logger)
        with stats.track_time("build_time"):
            mgr = self._env.formula_manager
            combined = (
                mgr.Or(self.phi, *(mgr.Not(lemma) for lemma in normalized_lemmas))
                if extended
                else mgr.And(self.phi, *normalized_lemmas)
            )
            if abstractor is None:
                abstractor = Abstractor()
            for atom in (*self.project_on, *sorted(combined.get_atoms(), key=FNode.node_id)):
                abstractor.get_id(atom)
            artifact = compiler.compile(
                combined, abstractor, project_on=self.project_on, computation_logger=computation_logger
            )
        stats.log("n_lemmas", len(normalized_lemmas))
        stats.log("n_projection_atoms", len(self.project_on))
        return TheoryCompiledTarget(artifact, abstractor, projection_atoms=self.project_on, env=self._env)

    def _normalize_atom(self, atom: FNode) -> FNode | None:
        positive = atom.arg(0) if atom.is_not() else atom
        if positive.is_bool_constant() or not is_atom(positive):
            raise ValueError("Projection entries must be Boolean symbols or theory atoms, optionally negated")
        normalized = self.normalize(atom)
        positive = normalized.arg(0) if normalized.is_not() else normalized
        # Valid atoms (including negated ones) that normalize to constants add no projection dimension.
        if positive.is_bool_constant():
            return None
        if not is_atom(positive):
            raise ValueError("Projection entries must normalize to Boolean symbols or theory atoms")
        return positive
