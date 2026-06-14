from __future__ import annotations

import pytest
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.typing import INT

from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import PropCompiler, QueryEngine


class BaseTestEngine:
    compiler_cls: type[PropCompiler]
    engine_cls: type[QueryEngine]
    _skip_queries: frozenset[str] = frozenset()

    @pytest.fixture
    def compiler(self, abstr) -> PropCompiler:
        return self.compiler_cls(abstr)

    @pytest.fixture
    def engine(self, compiler, abstr, mgr, a, b) -> QueryEngine:
        target = compiler.compile(mgr.And(a, b))
        return self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))

    def _skip_if(self, *queries: str) -> None:
        if any(q in self._skip_queries for q in queries):
            pytest.skip(f"unsupported by {self.engine_cls.__name__}")

    def test_is_satisfiable_false(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("is_satisfiable")
        target = compiler.compile(mgr.FALSE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[]))
        assert not engine.is_satisfiable()

    def test_is_satisfiable_true(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("is_satisfiable")
        target = compiler.compile(mgr.TRUE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[]))
        assert engine.is_satisfiable()

    def test_is_satisfiable_and(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("is_satisfiable")
        target = compiler.compile(mgr.And(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.is_satisfiable()

    def test_is_satisfiable_contradiction(self, mgr: FormulaManager, compiler, abstr, a: FNode) -> None:
        self._skip_if("is_satisfiable")
        target = compiler.compile(mgr.And(a, mgr.Not(a)))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a]))
        assert not engine.is_satisfiable()

    def test_is_satisfiable_under_assumptions_true(
        self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode
    ) -> None:
        self._skip_if("is_satisfiable")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.is_satisfiable(assumptions=[a])

    def test_is_satisfiable_under_assumptions_false(
        self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode
    ) -> None:
        self._skip_if("is_satisfiable")
        target = compiler.compile(mgr.And(a, mgr.Not(b)))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert not engine.is_satisfiable(assumptions=[mgr.Not(a)])

    def test_is_valid_true(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("is_valid")
        target = compiler.compile(mgr.TRUE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[]))
        assert engine.is_valid()

    def test_is_valid_tautology(self, mgr: FormulaManager, compiler, abstr, a: FNode) -> None:
        self._skip_if("is_valid")
        target = compiler.compile(mgr.Or(a, mgr.Not(a)))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a]))
        assert engine.is_valid()

    def test_is_valid_non_tautology(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("is_valid")
        target = compiler.compile(mgr.And(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert not engine.is_valid()

    def test_count_truth_assignments_and(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.And(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.count_truth_assignments() == 1

    def test_count_truth_assignments_or(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.count_truth_assignments() == 3

    def test_count_truth_assignments_true(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.TRUE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[]))
        assert engine.count_truth_assignments() > 0

    def test_count_truth_assignments_under_assumptions(
        self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode
    ) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.count_truth_assignments(assumptions=[a]) == 2

    def test_count_truth_assignments_under_assumptions_negated(
        self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode
    ) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.count_truth_assignments(assumptions=[mgr.Not(a)]) == 1

    def test_count_truth_assignments_under_full_assumptions(
        self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode
    ) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.count_truth_assignments(assumptions=[a, b]) == 1

    def test_count_truth_assignments_under_contradictory_assumptions(
        self, mgr: FormulaManager, compiler, abstr, a: FNode
    ) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.Or(a, mgr.Not(a)))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a]))
        assert engine.count_truth_assignments(assumptions=[a, mgr.Not(a)]) == 0

    def test_entails_clause_trivial(self, engine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        self._skip_if("entails_clause")
        assert engine.entails_clause(a)
        assert engine.entails_clause(b)
        assert engine.entails_clause(mgr.Or(a, b))

    def test_entails_clause_false_target(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("entails_clause")
        abstr.get_id(a)
        abstr.get_id(b)
        target = compiler.compile(mgr.FALSE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.entails_clause(a)
        assert engine.entails_clause(mgr.Not(a))
        assert engine.entails_clause(mgr.Or(a, b))

    def test_entails_clause_not_entailed(self, engine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        self._skip_if("entails_clause")
        assert not engine.entails_clause(mgr.Not(a))
        assert not engine.entails_clause(mgr.Not(b))

    def test_entails_clause_tautology(self, engine, mgr: FormulaManager) -> None:
        self._skip_if("entails_clause")
        assert engine.entails_clause(mgr.TRUE())

    def test_is_implicant_trivial(self, engine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        self._skip_if("is_implicant")
        assert engine.is_implicant(mgr.And(a, b))
        assert not engine.is_implicant(a)
        assert not engine.is_implicant(b)

    def test_is_implicant_not_implicant(self, engine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        self._skip_if("is_implicant")
        assert not engine.is_implicant(mgr.And(mgr.Not(a), b))
        assert not engine.is_implicant(mgr.Not(a))

    def test_is_implicant_or(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("is_implicant")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.is_implicant(a)
        assert engine.is_implicant(b)
        assert engine.is_implicant(mgr.And(a, mgr.Not(b)))
        assert not engine.is_implicant(mgr.And(mgr.Not(a), mgr.Not(b)))

    def test_is_implicant_false_target(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("is_implicant")
        abstr.get_id(a)
        abstr.get_id(b)
        target = compiler.compile(mgr.FALSE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.is_implicant(mgr.And(a, mgr.Not(a)))
        assert engine.is_implicant(mgr.FALSE())

    def test_is_implicant_invalid_input(self, engine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        self._skip_if("is_implicant")
        with pytest.raises(ValueError):
            engine.is_implicant(mgr.Or(a, b))

    def test_enumerate_truth_assignments_and(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("enumerate_truth_assignments")
        target = compiler.compile(mgr.And(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 1
        assert assignments[0] == {a: True, b: True}

    def test_enumerate_truth_assignments_or(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("enumerate_truth_assignments")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 3
        assert {a: True, b: True} in assignments
        assert {a: True, b: False} in assignments
        assert {a: False, b: True} in assignments

    def test_enumerate_truth_assignments_false(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("enumerate_truth_assignments")
        target = compiler.compile(mgr.FALSE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[]))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 0

    def test_enumerate_truth_assignments_theory(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("enumerate_truth_assignments")
        x = mgr.Symbol("x", INT)
        f1 = mgr.GT(x, mgr.Int(0))
        f2 = mgr.LE(x, mgr.Int(10))
        target = compiler.compile(mgr.And(f1, f2))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[f1, f2]))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 1
        assert assignments[0] == {f1: True, f2: True}

    def test_theory_atoms(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("is_satisfiable", "count_truth_assignments", "entails_clause")
        x = mgr.Symbol("x", INT)
        f1 = mgr.GT(x, mgr.Int(0))
        f2 = mgr.LE(x, mgr.Int(10))
        target = compiler.compile(mgr.And(f1, f2))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[f1, f2]))
        assert engine.is_satisfiable()
        assert engine.count_truth_assignments() == 1
        assert engine.entails_clause(f1)
        assert engine.entails_clause(f2)

    def test_multiple_queries(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("is_satisfiable", "count_truth_assignments", "entails_clause")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.is_satisfiable()
        assert engine.count_truth_assignments() == 3
        assert engine.entails_clause(mgr.Or(a, b))
        assert not engine.entails_clause(mgr.Or(mgr.Not(a), mgr.Not(b)))

    def test_is_satisfiable_unknown_assumption(self, engine, mgr: FormulaManager, c: FNode) -> None:
        self._skip_if("is_satisfiable")
        with pytest.raises(ValueError, match="not a care variable"):
            engine.is_satisfiable(assumptions=[c])

    def test_count_truth_assignments_unknown_assumption(self, engine, mgr: FormulaManager, c: FNode) -> None:
        self._skip_if("count_truth_assignments")
        with pytest.raises(ValueError, match="not a care variable"):
            engine.count_truth_assignments(assumptions=[c])

    def test_entails_clause_unknown_atom(self, engine, mgr: FormulaManager, c: FNode) -> None:
        self._skip_if("entails_clause")
        with pytest.raises(ValueError, match="not a care variable"):
            engine.entails_clause(c)

    def test_is_implicant_unknown_atom(self, engine, mgr: FormulaManager, c: FNode) -> None:
        self._skip_if("is_implicant")
        with pytest.raises(ValueError, match="not a care variable"):
            engine.is_implicant(c)

    # --- Projection tests ---

    def test_projected_count_smaller(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode, c: FNode) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.And(a, mgr.Or(b, c)), project_on=[a, b])
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.count_truth_assignments() == 2

    def test_projected_count_full(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode, c: FNode) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.And(a, mgr.Or(b, c)))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b, c]))
        assert engine.count_truth_assignments() == 3

    def test_projected_enumerate(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode, c: FNode) -> None:
        self._skip_if("enumerate_truth_assignments")
        target = compiler.compile(mgr.And(a, mgr.Or(b, c)), project_on=[a, b])
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 2
        assert all(set(assg.keys()) == {a, b} for assg in assignments)

    def test_projected_with_assumptions(
        self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode, c: FNode
    ) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.And(a, mgr.Or(b, c)), project_on=[a, b])
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.count_truth_assignments(assumptions=[a]) == 2
        assert engine.count_truth_assignments(assumptions=[mgr.Not(a)]) == 0

    def test_projected_theory_atoms(self, mgr: FormulaManager, compiler, abstr, a: FNode) -> None:
        self._skip_if("count_truth_assignments")
        x = mgr.Symbol("x", INT)
        f1 = mgr.GT(x, mgr.Int(0))
        f2 = mgr.LE(x, mgr.Int(10))
        target = compiler.compile(mgr.And(f1, mgr.Or(a, f2)), project_on=[a])
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a]))
        assert engine.count_truth_assignments() == 2

    def test_projected_assumption_on_forgotten_var_raises(
        self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode, c: FNode
    ) -> None:
        self._skip_if("is_satisfiable", "count_truth_assignments")
        target = compiler.compile(mgr.And(a, mgr.Or(b, c)), project_on=[a, b])
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        with pytest.raises(ValueError, match="not a care variable"):
            engine.is_satisfiable(assumptions=[c])
        with pytest.raises(ValueError, match="not a care variable"):
            engine.count_truth_assignments(assumptions=[c])

    # Non-contiguous care var ID tests (care var IDs not starting at 1)

    def test_projected_count_non_contiguous_ids(
        self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode, c: FNode
    ) -> None:
        self._skip_if("count_truth_assignments")
        abstr.get_id(c)
        abstr.get_id(a)
        abstr.get_id(b)
        target = compiler.compile(mgr.And(a, mgr.Or(b, c)), project_on=[a, b])
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.count_truth_assignments() == 2

    def test_projected_count_non_contiguous_ids_reverse(
        self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode, c: FNode
    ) -> None:
        self._skip_if("count_truth_assignments")
        abstr.get_id(a)
        abstr.get_id(c)
        abstr.get_id(b)
        target = compiler.compile(mgr.And(a, mgr.Or(b, c)), project_on=[b, c])
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[b, c]))
        assert engine.count_truth_assignments() == 3

    def test_projected_assumptions_non_first_var(
        self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode, c: FNode
    ) -> None:
        self._skip_if("count_truth_assignments")
        abstr.get_id(c)
        abstr.get_id(a)
        abstr.get_id(b)
        target = compiler.compile(mgr.And(a, mgr.Or(b, c)), project_on=[a, b])
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assert engine.count_truth_assignments(assumptions=[a]) == 2
        assert engine.count_truth_assignments(assumptions=[b]) == 1

    def test_projected_enumerate_non_contiguous_ids(
        self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode, c: FNode
    ) -> None:
        self._skip_if("enumerate_truth_assignments")
        abstr.get_id(c)
        abstr.get_id(a)
        abstr.get_id(b)
        target = compiler.compile(mgr.And(a, mgr.Or(b, c)), project_on=[a, b])
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 2
        assert all(set(assg.keys()) == {a, b} for assg in assignments)
        assert {a: True, b: False} in assignments
        assert {a: True, b: True} in assignments
