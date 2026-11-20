from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Self

from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import get_env

from tddnnf.compilation.compiler import PropCompiler
from tddnnf.compilation.targets import T_Target, TheoryCompiledTarget
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.pysmt_utils import is_atom, owns_dags
from tddnnf.core.stats_collector import StatsCollector
from tddnnf.normalization.normalizer import NormalizerWalker


class TheoryCompilation:
    """Entry point for SMT-level Knowledge Compilation.

    Given an SMT formula and a superset of its atoms, this class exposes high-level methods for compiling theory-reduced
    and theory-extended equivalent formulas into some target compilation language.
    The class is responsible for:
    - correctly constructing the mapping between atoms and indices representing their Boolean abstraction. Theory-atoms
      are normalized to a canonical form.
    - properly combining the formula with a supplied set of theory-lemmas, so to build a theory-equivalent formula that
      is either theory-reduced or theory-extended.
    - invoking the supplied Boolean compiler on the Boolean abstraction of the theory-reduced or theory-extended formula
    - constructing the `TheoryCompilationTarget` with the atom mapping and the compiled Boolean abstraction.
    """

    def __init__(
        self,
        phi: FNode,
        atoms: Sequence[FNode] | None = None,
        env: Environment | None = None,
    ) -> None:
        """Create a compilation context.

        Args:
            phi: The formula to compile.
            atoms: The superset of atoms to consider the formula over.
            env: The PySMT environment.
        """
        self._env = env if env is not None else get_env()
        self._closed = False
        self._normalizer = None
        try:
            self._normalizer = NormalizerWalker(self._env)
            self.phi = self.normalize(phi)
            atoms = sorted(self.phi.get_atoms(), key=FNode.node_id) if atoms is None else atoms
            self.atoms = tuple(
                dict.fromkeys(normalized for atom in atoms if (normalized := self._normalize_atom(atom)) is not None)
            )
            if not self.phi.get_atoms() <= set(self.atoms):
                raise ValueError("Normalized formula atoms must belong to atoms")
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> Self:
        self._ensure_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._closed = True
        if self._normalizer is not None:
            self._normalizer.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Compilation session is closed")

    def normalize(self, formula: FNode) -> FNode:
        """Normalize an SMT formula using the session normalizer.

        Args:
            formula: The formula to normalize.

        Returns:
            FNode: The normalized formula.
        """
        self._ensure_open()
        assert self._normalizer is not None
        return self._normalizer.normalize(formula)

    def compile_treduced(
        self,
        compiler: PropCompiler[T_Target],
        lemmas: Iterable[FNode],
        computation_logger: dict[str, object] | None = None,
        *,
        exists_atoms: Sequence[FNode] | None = None,
        abstractor: Abstractor | None = None,
    ) -> TheoryCompiledTarget[T_Target]:
        """Compile a theory-reduced formula theory-equivalent to self.phi in the `T_Target` compilation language.

        Using `PropCompiler`, compile the Boolean abstraction of `exists V. exists W. (phi and L)`, where:
        - `phi` is the formula to be compiled. `atoms(phi)` must be a subset of `self.atoms`.
        - `L` is the conjunction of the supplied `lemmas`
        - `W` is the subset of theory atoms appearing in L but not in atoms.
        - `V` is the set of atoms `exists_atoms`

        Args:
            compiler: Boolean compiler to use.
            lemmas: Set of theory-lemmas that must rule out the theory-inconsistent truth assignments over `self.atoms`
                that propositionally satisfy `self.phi`.
            computation_logger: Dictionary where to store compilation statistics.
            exists_atoms: Set of atoms to existentially quantify during compilation.
            abstractor: Mapping between atoms and indices.

        Returns:
            TheoryCompiledTarget[T_Target]: The theory-reduced compiled SMT formula.
        """
        return self._compile(compiler, lemmas, False, exists_atoms, computation_logger, abstractor)

    def compile_textended(
        self,
        compiler: PropCompiler[T_Target],
        lemmas: Iterable[FNode],
        computation_logger: dict[str, object] | None = None,
        *,
        abstractor: Abstractor | None = None,
    ) -> TheoryCompiledTarget[T_Target]:
        """Compile a theory-extended formula theory-equivalent to self.phi in the `T_Target` compilation language.

        Using `PropCompiler`, compile the Boolean abstraction of `forall W. (phi or not L)`, where:
        - `phi` is the formula to be compiled. `atoms(phi)` must be a subset of `self.atoms`.
        - `L` is the conjunction of the supplied `lemmas`.
        - `W` is the subset of theory atoms appearing in L but not in atoms.

        Args:
            compiler: Boolean compiler to use.
            lemmas: Set of theory-lemmas that must rule out the theory-inconsistent truth assignments over `self.atoms`
                that propositionally satisfy `(not self.phi)`.
            computation_logger: Dictionary where to store compilation statistics.
            abstractor: Mapping between atoms and IDs.

        Returns:
            TheoryCompiledTarget[T_Target]: The theory-extended compiled SMT formula.
        """
        return self._compile(compiler, lemmas, True, (), computation_logger, abstractor)

    def _compile(
        self,
        compiler: PropCompiler[T_Target],
        lemmas: Iterable[FNode],
        extended: bool,
        exists_atoms: Sequence[FNode] | None,
        computation_logger: dict[str, object] | None = None,
        abstractor: Abstractor | None = None,
    ) -> TheoryCompiledTarget[T_Target]:
        self._ensure_open()
        if isinstance(compiler, (str, type)) or not isinstance(compiler, PropCompiler):
            raise TypeError("Expected a configured compiler instance")
        if abstractor is not None and not owns_dags(self._env, abstractor.id_to_atom.values()):
            raise ValueError("Abstraction must belong to the selected environment")
        if exists_atoms and extended:
            raise ValueError("Existential quantification for theory-extended formulas is currently unsupported")
        exists_atoms_set = set(exists_atoms or ())
        if not exists_atoms_set.issubset(self.atoms):
            raise ValueError("The set of atoms to existentially quantify must be a subset of the compilation atoms")
        retained_atoms = tuple(atom for atom in self.atoms if atom not in exists_atoms_set)
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
            extra_atoms_in_lemmas = combined.get_atoms() - set(self.atoms)
            quantified = tuple(sorted(exists_atoms_set | extra_atoms_in_lemmas, key=FNode.node_id))
            all_atoms = (*self.atoms, *sorted(extra_atoms_in_lemmas, key=FNode.node_id))
            for atom in all_atoms:
                abstractor.get_id(atom)
            artifact = compiler.compile(
                combined,
                abstractor,
                all_atoms=all_atoms,
                exists_atoms=() if extended else quantified,
                forall_atoms=quantified if extended else (),
                computation_logger=computation_logger,
            )
        stats.log("n_lemmas", len(normalized_lemmas))
        stats.log("n_projection_atoms", len(retained_atoms))
        return TheoryCompiledTarget(artifact, abstractor, atoms=retained_atoms, env=self._env)

    def _normalize_atom(self, atom: FNode) -> FNode | None:
        """Rewrite atom into a normal form."""
        positive = atom.arg(0) if atom.is_not() else atom
        if positive.is_bool_constant() or not is_atom(positive):
            raise ValueError("Vocabulary entries must be Boolean symbols or theory atoms, optionally negated")
        normalized = self.normalize(atom)
        positive = normalized.arg(0) if normalized.is_not() else normalized
        # Valid atoms (including negated ones) that normalize to constants add no vocabulary dimension.
        if positive.is_bool_constant():
            return None
        if not is_atom(positive):
            raise ValueError("Vocabulary entries must normalize to Boolean symbols or theory atoms")
        return positive
