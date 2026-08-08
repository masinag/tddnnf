from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import get_env

from tddnnf.builders.extended import TExtendedBuilder
from tddnnf.builders.reduced import TReducedBuilder
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import PropCompiler, QueryEngine, T_Target
from tddnnf.normalization.normalizer import NormalizerWalker
from tddnnf.queries.normalizing import NormalizingQueryEngine


class CompilationContext:
    """Normalized inputs for a KCMT compilation workflow."""

    def __init__(
        self,
        phi: FNode,
        project_on: Iterable[FNode] | None = None,
        env: Environment | None = None,
    ) -> None:
        """Normalize a formula and its projection atoms.

        Args:
            phi: Formula to compile.
            project_on: Atoms retained by compilation. Defaults to atoms in
                normalized ``phi`` when omitted.
            env: PySMT environment used for normalization and compilation.
        """
        self._env = env if env is not None else get_env()
        self._normalizer = NormalizerWalker(self._env)
        self.phi = self.normalize(phi)
        atoms = self.phi.get_atoms() if project_on is None else project_on
        self.project_on = list(dict.fromkeys(self._normalize_atom(atom) for atom in atoms))

    def normalize(self, formula: FNode) -> FNode:
        """Normalize a formula."""
        return self._normalizer.normalize(formula)

    def compile_treduced(
        self,
        compiler_type: type[PropCompiler[T_Target]],
        lemmas: Iterable[FNode],
        computation_logger: dict[str, object] | None = None,
    ) -> TheoryCompiledTarget[T_Target]:
        """Compile normalized inputs using the T-reduced strategy."""
        normalized_lemmas = [self.normalize(lemma) for lemma in lemmas]
        abstractor = Abstractor()
        compiler = compiler_type(abstractor, computation_logger=computation_logger)
        return TReducedBuilder(
            compiler,
            env=self._env,
            computation_logger=computation_logger,
        ).build(
            self.phi,
            normalized_lemmas,
            abstractor,
            project_on=self.project_on,
        )

    def compile_textended(
        self,
        compiler_type: type[PropCompiler[T_Target]],
        lemmas: Iterable[FNode],
        computation_logger: dict[str, object] | None = None,
    ) -> TheoryCompiledTarget[T_Target]:
        """Compile normalized inputs using the T-extended strategy."""
        normalized_lemmas = [self.normalize(lemma) for lemma in lemmas]
        abstractor = Abstractor()
        compiler = compiler_type(abstractor, computation_logger=computation_logger)
        return TExtendedBuilder(
            compiler,
            env=self._env,
            computation_logger=computation_logger,
        ).build(
            self.phi,
            normalized_lemmas,
            abstractor,
            project_on=self.project_on,
        )

    def _normalize_atom(self, atom: FNode) -> FNode:
        """Normalize an atom to its positive canonical representation."""
        normalized = self.normalize(atom)
        return normalized.arg(0) if normalized.is_not() else normalized


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
