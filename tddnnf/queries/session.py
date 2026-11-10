from __future__ import annotations

from collections.abc import Generator, Sequence
from contextlib import ExitStack
from typing import TYPE_CHECKING, Generic, Self

from pysmt.fnode import FNode

from tddnnf.core.interfaces import QueryEngine, T_Target
from tddnnf.core.pysmt_utils import is_literal, normalize_assumptions
from tddnnf.normalization.normalizer import NormalizerWalker

if TYPE_CHECKING:
    from collections.abc import Iterable

    from tddnnf.core.containers import TheoryCompiledTarget


class QuerySession(Generic[T_Target]):
    """Normalize, validate, and delegate queries in the target's environment."""

    def __init__(self, target: TheoryCompiledTarget[T_Target], engine_type: type[QueryEngine[T_Target]]):
        self._closed = False
        self._normalizer = None
        self._inner = None
        self._atom_index = {}
        self._iterators: set[Generator[dict[FNode, bool], None, None]] = set()
        self._atoms = target.projection_atoms
        self._mgr = target.env.formula_manager
        try:
            if not isinstance(engine_type, type) or not issubclass(engine_type, QueryEngine):
                raise TypeError("Expected a query engine class")
            self._normalizer = NormalizerWalker(target.env)
            self._atom_index = self._index_atoms(self._atoms)
            self._inner = engine_type(target)
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> Self:
        self._ensure_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Query session is closed")

    def close(self) -> None:
        """Release active iterators and native resources, once."""
        if self._closed:
            return
        self._closed = True
        with ExitStack() as cleanup:
            if self._normalizer is not None:
                cleanup.callback(self._normalizer.close)
            self._atom_index.clear()
            if self._inner is not None:
                close = getattr(self._inner, "close", None)
                if close is not None:
                    cleanup.callback(close)
            self._inner = None
            iterators = tuple(self._iterators)
            self._iterators.clear()
            for iterator in iterators:
                cleanup.callback(iterator.close)

    def _literals(self, inputs: Sequence[FNode], connective: str | None = None) -> list[FNode] | None:
        self._ensure_open()
        aligned = []
        stack = list(reversed(inputs))
        while stack:
            literal = stack.pop()
            if not isinstance(literal, FNode):
                raise ValueError("Expected Boolean literals")
            if connective is not None and getattr(literal, connective)():
                stack.extend(reversed(literal.args()))
            elif is_literal(literal):
                aligned.append(self._align_literal(literal))
            else:
                raise ValueError("Expected literals in assumptions, a clause, or a cube")
        # Validate every entry before handling constants or contradictions.
        absorbing = False if connective != "is_or" else True
        constants = [lit.constant_value() for lit in aligned if lit.is_bool_constant()]
        if absorbing in constants:
            return None
        return normalize_assumptions([lit for lit in aligned if not lit.is_bool_constant()])

    def is_satisfiable(self, assumptions: list[FNode] | None = None) -> bool:
        lits = self._literals([] if assumptions is None else assumptions)
        assert self._inner is not None
        return False if lits is None else self._inner.is_satisfiable(lits)

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        lits = self._literals([] if assumptions is None else assumptions)
        assert self._inner is not None
        return 0 if lits is None else self._inner.count_truth_assignments(lits)

    def is_valid(self) -> bool:
        self._ensure_open()
        assert self._inner is not None
        return self._inner.is_valid()

    def entails_clause(self, query_clause: FNode) -> bool:
        lits = self._literals([query_clause], "is_or")
        if lits is None:
            return True
        assert self._inner is not None
        return not self._inner.is_satisfiable([self._mgr.Not(lit) for lit in lits])

    def is_implicant(self, query_cube: FNode) -> bool:
        lits = self._literals([query_cube], "is_and")
        if lits is None:
            return True
        assert self._inner is not None
        return self._inner.is_implicant(self._mgr.And(lits))

    def enumerate_truth_assignments(self) -> Generator[dict[FNode, bool], None, None]:
        self._ensure_open()

        def assignments():
            inner = None
            try:
                assert self._inner is not None
                inner = self._inner.enumerate_truth_assignments()
                for assignment in inner:
                    yield {atom: assignment[atom] for atom in self._atoms}
            finally:
                self._iterators.discard(iterator)
                close = getattr(inner, "close", None)
                if close is not None:
                    close()

        iterator = assignments()
        self._iterators.add(iterator)
        return iterator

    def _index_atoms(self, atoms: Iterable[FNode]) -> dict[FNode, tuple[FNode, bool]]:
        """Index normalized atoms by exact target atom and polarity."""
        index: dict[FNode, tuple[FNode, bool]] = {}
        for target_atom in atoms:
            canonical, target_negated = self._normalize_with_polarity(target_atom)
            assert not canonical.is_bool_constant(), "Projection atoms must not normalize to constants"
            previous = index.get(canonical)
            if previous is not None and previous[0] != target_atom:
                raise ValueError(f"Ambiguous normalized atom {canonical}: {previous[0]}, {target_atom}")
            index[canonical] = (target_atom, target_negated)
        return index

    def _normalize_with_polarity(self, formula: FNode) -> tuple[FNode, bool]:
        """Return a positive normalized atom and its normalized polarity."""
        assert self._normalizer is not None
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
        if canonical.is_bool_constant():
            return self._mgr.Bool(canonical.is_true() ^ query_negated)
        target_atom, target_negated = self._lookup_atom(canonical, literal)
        aligned_negated = query_negated ^ target_negated
        if aligned_negated:
            return self._mgr.Not(target_atom)
        return target_atom
