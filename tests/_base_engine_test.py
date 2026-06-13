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
        return self.engine_cls(TheoryCompiledTarget(target, abstr))

    def _skip_if(self, *queries: str) -> None:
        if any(q in self._skip_queries for q in queries):
            pytest.skip(f"unsupported by {self.engine_cls.__name__}")

    def test_is_satisfiable_true(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("is_satisfiable")
        target = compiler.compile(mgr.TRUE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.is_satisfiable()

    def test_is_satisfiable_false(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("is_satisfiable")
        target = compiler.compile(mgr.FALSE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert not engine.is_satisfiable()

    def test_is_satisfiable_and(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("is_satisfiable")
        target = compiler.compile(mgr.And(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.is_satisfiable()

    def test_is_satisfiable_contradiction(self, mgr: FormulaManager, compiler, abstr, a: FNode) -> None:
        self._skip_if("is_satisfiable")
        target = compiler.compile(mgr.And(a, mgr.Not(a)))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert not engine.is_satisfiable()

    def test_is_valid_true(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("is_valid")
        target = compiler.compile(mgr.TRUE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.is_valid()

    def test_is_valid_tautology(self, mgr: FormulaManager, compiler, abstr, a: FNode) -> None:
        self._skip_if("is_valid")
        target = compiler.compile(mgr.Or(a, mgr.Not(a)))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.is_valid()

    def test_is_valid_non_tautology(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("is_valid")
        target = compiler.compile(mgr.And(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert not engine.is_valid()

    def test_count_truth_assignments_and(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.And(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.count_truth_assignments() == 1

    def test_count_truth_assignments_or(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.count_truth_assignments() == 3

    def test_count_truth_assignments_true(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.TRUE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.count_truth_assignments() > 0

    def test_count_truth_assignments_under_cube(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.count_truth_assignments(a) == 2

    def test_count_truth_assignments_under_cube_negated(
        self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode
    ) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.count_truth_assignments(mgr.Not(a)) == 1

    def test_count_truth_assignments_under_full_cube(
        self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode
    ) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.count_truth_assignments(mgr.And(a, b)) == 1

    def test_count_truth_assignments_under_contradictory_cube(
        self, mgr: FormulaManager, compiler, abstr, a: FNode
    ) -> None:
        self._skip_if("count_truth_assignments")
        target = compiler.compile(mgr.Or(a, mgr.Not(a)))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.count_truth_assignments(mgr.And(a, mgr.Not(a))) == 0

    def test_clause_entails_trivial(self, engine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        self._skip_if("clause_entails")
        assert engine.clause_entails(a)
        assert engine.clause_entails(b)
        assert engine.clause_entails(mgr.Or(a, b))

    def test_clause_entails_false_target(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("clause_entails")
        abstr.get_id(a)
        abstr.get_id(b)
        target = compiler.compile(mgr.FALSE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.clause_entails(a)
        assert engine.clause_entails(mgr.Not(a))
        assert engine.clause_entails(mgr.Or(a, b))

    def test_clause_entails_not_entailed(self, engine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        self._skip_if("clause_entails")
        assert not engine.clause_entails(mgr.Not(a))
        assert not engine.clause_entails(mgr.Not(b))

    def test_clause_entails_tautology(self, engine, mgr: FormulaManager) -> None:
        self._skip_if("clause_entails")
        assert engine.clause_entails(mgr.TRUE())

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
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.is_implicant(a)
        assert engine.is_implicant(b)
        assert engine.is_implicant(mgr.And(a, mgr.Not(b)))
        assert not engine.is_implicant(mgr.And(mgr.Not(a), mgr.Not(b)))

    def test_is_implicant_false_target(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("is_implicant")
        abstr.get_id(a)
        abstr.get_id(b)
        target = compiler.compile(mgr.FALSE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.is_implicant(mgr.And(a, mgr.Not(a)))
        assert engine.is_implicant(mgr.FALSE())

    def test_is_implicant_invalid_input(self, engine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        self._skip_if("is_implicant")
        with pytest.raises(ValueError):
            engine.is_implicant(mgr.Or(a, b))

    def test_enumerate_truth_assignments_and(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("enumerate_truth_assignments")
        target = compiler.compile(mgr.And(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 1
        assert assignments[0] == {a: True, b: True}

    def test_enumerate_truth_assignments_or(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("enumerate_truth_assignments")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 3
        assert {a: True, b: True} in assignments
        assert {a: True, b: False} in assignments
        assert {a: False, b: True} in assignments

    def test_enumerate_truth_assignments_false(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("enumerate_truth_assignments")
        target = compiler.compile(mgr.FALSE())
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 0

    def test_enumerate_truth_assignments_theory(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("enumerate_truth_assignments")
        x = mgr.Symbol("x", INT)
        f1 = mgr.GT(x, mgr.Int(0))
        f2 = mgr.LE(x, mgr.Int(10))
        formula = mgr.And(f1, f2)
        target = compiler.compile(formula)
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 1
        assert assignments[0] == {f1: True, f2: True}

    def test_theory_atoms(self, mgr: FormulaManager, compiler, abstr) -> None:
        self._skip_if("is_satisfiable", "count_truth_assignments", "clause_entails")
        x = mgr.Symbol("x", INT)
        f1 = mgr.GT(x, mgr.Int(0))
        f2 = mgr.LE(x, mgr.Int(10))
        formula = mgr.And(f1, f2)
        target = compiler.compile(formula)
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.is_satisfiable()
        assert engine.count_truth_assignments() == 1
        assert engine.clause_entails(f1)
        assert engine.clause_entails(f2)

    def test_multiple_queries(self, mgr: FormulaManager, compiler, abstr, a: FNode, b: FNode) -> None:
        self._skip_if("is_satisfiable", "count_truth_assignments", "clause_entails")
        target = compiler.compile(mgr.Or(a, b))
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr))
        assert engine.is_satisfiable()
        assert engine.count_truth_assignments() == 3
        assert engine.clause_entails(mgr.Or(a, b))
        assert not engine.clause_entails(mgr.Or(mgr.Not(a), mgr.Not(b)))
