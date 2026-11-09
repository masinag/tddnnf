from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Self

from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import get_env
from pysmt.smtlib.printers import to_smtlib

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import PropCompiler, QueryEngine, T_Target
from tddnnf.core.pysmt_utils import is_atom
from tddnnf.core.stats_collector import StatsCollector
from tddnnf.normalization.normalizer import NormalizerWalker
from tddnnf.queries.normalizing import NormalizingQueryEngine


class TheoryCompilation:
    """Normalize inputs and compile either theory construction through one pipeline.

    Callers must provide Boolean FNodes for phi and lemmas, with all input DAGs
    (including projection entries) belonging to the selected environment.
    These type and environment preconditions are not checked at runtime.
    """

    def __init__(
        self,
        phi: FNode,
        project_on: Iterable[FNode] | None = None,
        env: Environment | None = None,
    ) -> None:
        self._env = env if env is not None else get_env()
        self._closed = False
        self._normalizer = None
        try:
            self._normalizer = NormalizerWalker(self._env)
            self.phi = self.normalize(phi)
            atoms = (
                sorted(self.phi.get_atoms(), key=lambda a: to_smtlib(a, daggify=False))
                if project_on is None
                else project_on
            )
            self.project_on = list(dict.fromkeys(self._normalize_atom(atom) for atom in atoms))
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
    ) -> TheoryCompiledTarget[T_Target]:
        """Conjoin theory lemmas enumerated over normalized phi."""
        return self._compile(compiler, lemmas, False, computation_logger)

    def compile_textended(
        self,
        compiler: PropCompiler[T_Target],
        lemmas: Iterable[FNode],
        computation_logger: dict[str, object] | None = None,
    ) -> TheoryCompiledTarget[T_Target]:
        """Disjoin negated theory lemmas enumerated over Not(phi)."""
        return self._compile(compiler, lemmas, True, computation_logger)

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
        abstractor = abstractor if abstractor is not None else Abstractor()
        stats = StatsCollector(computation_logger)
        with stats.track_time("build_time"):
            mgr = self._env.formula_manager
            combined = (
                mgr.Or(self.phi, *(mgr.Not(lemma) for lemma in normalized_lemmas))
                if extended
                else mgr.And(self.phi, *normalized_lemmas)
            )
            for atom in self.project_on:
                abstractor.get_id(atom)
            for atom in sorted(combined.get_atoms(), key=lambda a: to_smtlib(a, daggify=False)):
                abstractor.get_id(atom)
            artifact = compiler.compile(
                combined, abstractor, project_on=self.project_on, computation_logger=computation_logger
            )
        stats.log("n_lemmas", len(normalized_lemmas))
        stats.log("n_projection_atoms", len(self.project_on))
        return TheoryCompiledTarget(artifact, abstractor, projection_atoms=list(self.project_on))

    def _normalize_atom(self, atom: FNode) -> FNode:
        normalized = self.normalize(atom)
        positive = normalized.arg(0) if normalized.is_not() else normalized
        if positive.is_bool_constant() or not is_atom(positive):
            raise ValueError("Projection entries must normalize to Boolean symbols or theory atoms")
        return positive


CompilationContext = TheoryCompilation


class QueryContext:
    """Align normalized queries with a target's exact ``projection_atoms``."""

    def __init__(self, target: TheoryCompiledTarget[Any], env: Environment | None = None) -> None:
        """Build a target atom index.

        Args:
            target: Compiled target whose projection atoms queries must use.
            env: PySMT environment used for query normalization.

        Raises:
            ValueError: If distinct projection atoms have one canonical form.
        """
        self._normalizer = NormalizerWalker(env)
        self._atom_index = self._index_atoms(target.projection_atoms)

    def wrap_queries(self, engine: QueryEngine[T_Target]) -> QueryEngine[T_Target]:
        """Return an engine that aligns query inputs before delegation."""
        return NormalizingQueryEngine(engine, self)

    def _index_atoms(self, atoms: Iterable[FNode]) -> dict[FNode, tuple[FNode, bool]]:
        """Index normalized atoms by exact target atom and polarity."""
        index: dict[FNode, tuple[FNode, bool]] = {}
        for target_atom in atoms:
            canonical, target_negated = self._normalize_with_polarity(target_atom)
            previous = index.get(canonical)
            if previous is not None and previous[0] != target_atom:
                raise ValueError(f"Ambiguous normalized atom {canonical}: {previous[0]}, {target_atom}")
            index[canonical] = (target_atom, target_negated)
        return index

    def _normalize_with_polarity(self, formula: FNode) -> tuple[FNode, bool]:
        """Return a positive normalized atom and its normalized polarity."""
        normalized = self._normalizer.normalize(formula)
        negated = normalized.is_not()
        return (normalized.arg(0) if negated else normalized), negated

    def _lookup_atom(self, canonical: FNode, query_atom: FNode) -> tuple[FNode, bool]:
        try:
            return self._atom_index[canonical]
        except KeyError as exc:
            raise ValueError(f"Query atom not in target projection_atoms: {query_atom.serialize()}") from exc

    def _align_literal(self, literal: FNode) -> FNode:
        """Normalize one literal and replace its atom with the target atom."""
        canonical, query_negated = self._normalize_with_polarity(literal)
        target_atom, target_negated = self._lookup_atom(canonical, literal)
        aligned_negated = query_negated ^ target_negated
        if aligned_negated:
            return self._normalizer.mgr.Not(target_atom)
        return target_atom

    def align_assumptions(self, assumptions: list[FNode] | None) -> list[FNode] | None:
        """Align assumptions with target projection atoms.

        Args:
            assumptions: Query literals, or ``None``.

        Returns:
            Aligned literals, or ``None``.

        Raises:
            ValueError: If an atom is absent from target projection atoms.
        """
        if assumptions is None:
            return None
        return [self._align_literal(literal) for literal in assumptions]

    def align_formula(self, formula: FNode) -> FNode:
        """Align a formula with target projection atoms.

        Args:
            formula: Query clause or cube.

        Returns:
            Aligned formula.

        Raises:
            ValueError: If an atom is absent from target projection atoms.
        """
        normalized = self._normalizer.normalize(formula)
        substitutions: dict[FNode, FNode] = {}
        for canonical in normalized.get_atoms():
            target_atom, target_negated = self._lookup_atom(canonical, canonical)
            substitutions[canonical] = self._normalizer.mgr.Not(target_atom) if target_negated else target_atom
        return self._normalizer.env.substituter.substitute(normalized, substitutions)
