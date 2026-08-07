from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.typing import BOOL, INT

from tddnnf.context import QueryContext
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import QueryEngine
from tddnnf.core.pysmt_utils import clause_lits, cube_lits


class RecordingEngine:
    def __init__(self) -> None:
        self.satisfiability_assumptions: list[FNode] | None = []
        self.counting_assumptions: list[FNode] | None = []
        self.clause: FNode | None = None
        self.cube: FNode | None = None
        self.calls: list[str] = []
        self.models: Iterator[dict[FNode, bool]] = iter(())

    def is_satisfiable(self, assumptions: list[FNode] | None = None) -> bool:
        self.calls.append("is_satisfiable")
        self.satisfiability_assumptions = assumptions
        return True

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        self.calls.append("count_truth_assignments")
        self.counting_assumptions = assumptions
        return 7

    def is_valid(self) -> bool:
        self.calls.append("is_valid")
        return True

    def entails_clause(self, query_clause: FNode) -> bool:
        self.calls.append("entails_clause")
        self.clause = query_clause
        return True

    def is_implicant(self, query_cube: FNode) -> bool:
        self.calls.append("is_implicant")
        self.cube = query_cube
        return True

    def enumerate_truth_assignments(self) -> Iterator[dict[FNode, bool]]:
        self.calls.append("enumerate_truth_assignments")
        return self.models


def _context(mgr: FormulaManager, *projection_atoms: FNode) -> QueryContext:
    target = cast(TheoryCompiledTarget[Any], SimpleNamespace(projection_atoms=list(projection_atoms)))
    return QueryContext(target, env=mgr.env)


def _relations(mgr: FormulaManager) -> tuple[FNode, FNode, FNode, FNode]:
    x = mgr.Symbol("normalizing_query_x", INT)
    y = mgr.Symbol("normalizing_query_y", INT)
    x_lt_y = mgr.LT(x, y)
    y_le_x = mgr.LE(y, x)
    x_ge_two = mgr.GE(x, mgr.Int(2))
    scaled_x_ge_two = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    return x_lt_y, y_le_x, x_ge_two, scaled_x_ge_two


def test_context_aligns_equivalent_atoms_and_polarity(mgr: FormulaManager) -> None:
    x_lt_y, y_le_x, compiled_atom, equivalent_atom = _relations(mgr)

    assert _context(mgr, compiled_atom).align_assumptions([equivalent_atom, mgr.Not(equivalent_atom)]) == [
        compiled_atom,
        mgr.Not(compiled_atom),
    ]
    assert _context(mgr, y_le_x).align_assumptions([x_lt_y, mgr.Not(x_lt_y)]) == [
        mgr.Not(y_le_x),
        y_le_x,
    ]
    assert _context(mgr, x_lt_y).align_assumptions([y_le_x, x_lt_y]) == [mgr.Not(x_lt_y), x_lt_y]


def test_context_rejects_ambiguous_atoms(mgr: FormulaManager) -> None:
    x_lt_y, y_le_x, _, _ = _relations(mgr)

    with pytest.raises(ValueError, match="Ambiguous normalized atom"):
        _context(mgr, x_lt_y, y_le_x)


def test_context_rejects_unknown_atom(mgr: FormulaManager) -> None:
    _, _, compiled_atom, _ = _relations(mgr)
    unknown = mgr.Symbol("normalizing_context_unknown", BOOL)
    context = _context(mgr, compiled_atom)

    with pytest.raises(ValueError, match="Query atom not in target projection_atoms: normalizing_context_unknown"):
        context.align_assumptions([unknown])
    with pytest.raises(ValueError, match="Query atom not in target projection_atoms: normalizing_context_unknown"):
        context.align_formula(mgr.Or(compiled_atom, unknown))


def test_context_aligns_nested_clause_and_cube(mgr: FormulaManager) -> None:
    _, _, compiled_atom, equivalent_atom = _relations(mgr)
    p = mgr.Symbol("normalizing_context_p", BOOL)
    q = mgr.Symbol("normalizing_context_q", BOOL)
    context = _context(mgr, p, q, compiled_atom)

    clause = context.align_formula(mgr.Or(p, mgr.Or(equivalent_atom, mgr.Not(q))))
    cube = context.align_formula(mgr.And(p, mgr.And(equivalent_atom, mgr.Not(q))))

    expected = {p, compiled_atom, mgr.Not(q)}
    assert set(clause_lits(clause) or []) == expected
    assert set(cube_lits(cube) or []) == expected


def test_context_preserves_none_assumptions(mgr: FormulaManager) -> None:
    _, _, compiled_atom, _ = _relations(mgr)

    assert _context(mgr, compiled_atom).align_assumptions(None) is None


def test_wrapper_aligns_query_inputs(mgr: FormulaManager) -> None:
    _, _, compiled_atom, equivalent_atom = _relations(mgr)
    p = mgr.Symbol("normalizing_query_p", BOOL)
    inner = RecordingEngine()
    engine = _context(mgr, p, compiled_atom).wrap_queries(inner)

    assert engine.is_satisfiable([equivalent_atom])
    assert engine.count_truth_assignments([mgr.Not(equivalent_atom)]) == 7
    engine.entails_clause(mgr.Or(p, equivalent_atom))
    engine.is_implicant(mgr.And(p, mgr.Not(equivalent_atom)))

    assert inner.satisfiability_assumptions == [compiled_atom]
    assert inner.counting_assumptions == [mgr.Not(compiled_atom)]
    assert inner.clause is not None
    assert set(clause_lits(inner.clause) or []) == {p, compiled_atom}
    assert inner.cube is not None
    assert set(cube_lits(inner.cube) or []) == {p, mgr.Not(compiled_atom)}


def test_wrapper_delegates_unchanged_inputs_and_outputs(mgr: FormulaManager) -> None:
    _, _, compiled_atom, _ = _relations(mgr)
    inner = RecordingEngine()
    engine = _context(mgr, compiled_atom).wrap_queries(inner)

    assert isinstance(engine, QueryEngine)
    assert engine.is_satisfiable(None)
    assert engine.count_truth_assignments(None) == 7
    assert engine.is_valid()
    assert engine.enumerate_truth_assignments() is inner.models
    assert inner.satisfiability_assumptions is None
    assert inner.counting_assumptions is None
    assert inner.calls == [
        "is_satisfiable",
        "count_truth_assignments",
        "is_valid",
        "enumerate_truth_assignments",
    ]


def test_wrapper_rejects_unknown_atom_before_delegation(mgr: FormulaManager) -> None:
    _, _, compiled_atom, _ = _relations(mgr)
    unknown = mgr.Symbol("normalizing_query_unknown", BOOL)
    inner = RecordingEngine()
    engine = _context(mgr, compiled_atom).wrap_queries(inner)

    with pytest.raises(ValueError, match="Query atom not in target projection_atoms: normalizing_query_unknown"):
        engine.is_satisfiable([unknown])
    assert inner.calls == []
