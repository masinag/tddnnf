from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import ExitStack
from typing import Self

from pysmt.fnode import FNode

from tddnnf.compilers.cudd import BddCompiledTarget
from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.compilers.pysdd import SddCompiledTarget
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.pysmt_utils import is_literal, normalize_assumptions
from tddnnf.queries.bdd_engine import BddEngine
from tddnnf.queries.d4_engine import D4Engine
from tddnnf.queries.sdd_engine import SddEngine


class CuddReasoner:
    """Configure native CUDD queries for a BddCompiledTarget."""


class SddReasoner:
    """Configure native PySDD queries for an SddCompiledTarget."""


class DdnnifeReasoner:
    """Configure native ddnnife queries for a D4CompiledTarget."""


class QuerySession:
    """Normalize, validate, and delegate queries in the target's environment."""

    def __init__(self, target: TheoryCompiledTarget, reasoner: CuddReasoner | SddReasoner | DdnnifeReasoner):
        from tddnnf.context import QueryContext

        pairings = {
            CuddReasoner: (BddCompiledTarget, BddEngine),
            SddReasoner: (SddCompiledTarget, SddEngine),
            DdnnifeReasoner: (D4CompiledTarget, D4Engine),
        }
        if type(reasoner) not in pairings:
            raise TypeError("Expected a configured reasoner instance")
        target_type, engine_type = pairings[type(reasoner)]
        if not isinstance(target.target, target_type):
            raise TypeError(f"{type(reasoner).__name__} requires {target_type.__name__}")
        self._closed = False
        self._context = None
        self._inner = None
        self._iterators: set[_Assignments] = set()
        self._atoms = target.projection_atoms
        self._mgr = target.env.formula_manager
        try:
            self._context = QueryContext(target, env=target.env)
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
        if hasattr(self, "_closed"):
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
            if self._context is not None:
                cleanup.callback(self._context.close)
            if self._inner is not None:
                close = getattr(self._inner, "close", None)
                if close is not None:
                    cleanup.callback(close)
            self._inner = None
            for iterator in tuple(self._iterators):
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
                aligned.append(self._context._align_literal(literal))
            else:
                raise ValueError("Expected literals in assumptions, a clause, or a cube")
        # Validate every entry before handling constants or contradictions.
        absorbing = False if connective != "is_or" else True
        constants = [lit.constant_value() for lit in aligned if lit.is_bool_constant()]
        unique = normalize_assumptions([lit for lit in aligned if not lit.is_bool_constant()])
        return None if absorbing in constants or unique is None else unique

    def is_satisfiable(self, assumptions: list[FNode] | None = None) -> bool:
        lits = self._literals([] if assumptions is None else assumptions)
        return False if lits is None else self._inner.is_satisfiable(lits)

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        lits = self._literals([] if assumptions is None else assumptions)
        return 0 if lits is None else self._inner.count_truth_assignments(lits)

    def is_valid(self) -> bool:
        self._ensure_open()
        if isinstance(self._inner, D4Engine):
            return self.count_truth_assignments() == 1 << len(self._atoms)
        return self._inner.is_valid()

    def entails_clause(self, query_clause: FNode) -> bool:
        lits = self._literals([query_clause], "is_or")
        if lits is None:
            return True
        return not self._inner.is_satisfiable([self._mgr.Not(lit) for lit in lits])

    def is_implicant(self, query_cube: FNode) -> bool:
        lits = self._literals([query_cube], "is_and")
        if lits is None:
            return True
        if isinstance(self._inner, D4Engine):
            return self._inner.count_truth_assignments(lits) == 1 << (len(self._atoms) - len(lits))
        return self._inner.is_implicant(self._mgr.And(lits))

    def enumerate_truth_assignments(self) -> Iterator[dict[FNode, bool]]:
        self._ensure_open()
        iterator = _Assignments(self, self._inner.enumerate_truth_assignments())
        self._iterators.add(iterator)
        return iterator


class _Assignments(Iterator[dict[FNode, bool]]):
    def __init__(self, session: QuerySession, inner: Iterator[dict[FNode, bool]]):
        self._session = session
        self._inner = inner

    def __next__(self) -> dict[FNode, bool]:
        self._session._ensure_open()
        if self._inner is None:
            raise StopIteration
        try:
            assignment = next(self._inner)
            return {atom: assignment[atom] for atom in self._session._atoms}
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        inner, self._inner = self._inner, None
        self._session._iterators.discard(self)
        if inner is not None:
            close = getattr(inner, "close", None)
            if close is not None:
                close()
