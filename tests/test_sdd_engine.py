from __future__ import annotations

import pytest
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.typing import INT

from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries.sdd_engine import SddEngine


class TestSddEngine:
    @pytest.fixture
    def compiler(self, abstr: Abstractor) -> SddCompiler:
        return SddCompiler(abstr)

    @pytest.fixture
    def engine(self, compiler: SddCompiler, abstr: Abstractor, mgr: FormulaManager, a: FNode, b: FNode) -> SddEngine:
        target = compiler.compile(mgr.And(a, b))
        return SddEngine(TheoryCompiledTarget(target, abstr))

    def test_is_satisfiable_true(self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor) -> None:
        target = compiler.compile(mgr.TRUE())
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.is_satisfiable()

    def test_is_satisfiable_false(self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor) -> None:
        target = compiler.compile(mgr.FALSE())
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert not engine.is_satisfiable()

    def test_is_satisfiable_and(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode, b: FNode
    ) -> None:
        target = compiler.compile(mgr.And(a, b))
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.is_satisfiable()

    def test_is_satisfiable_contradiction(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode
    ) -> None:
        target = compiler.compile(mgr.And(a, mgr.Not(a)))
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert not engine.is_satisfiable()

    def test_is_valid_true(self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor) -> None:
        target = compiler.compile(mgr.TRUE())
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.is_valid()

    def test_is_valid_tautology(self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode) -> None:
        target = compiler.compile(mgr.Or(a, mgr.Not(a)))
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.is_valid()

    def test_is_valid_non_tautology(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode, b: FNode
    ) -> None:
        target = compiler.compile(mgr.And(a, b))
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert not engine.is_valid()

    def test_count_truth_assignments_and(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode, b: FNode
    ) -> None:
        target = compiler.compile(mgr.And(a, b))
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.count_truth_assignments() == 1

    def test_count_truth_assignments_or(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode, b: FNode
    ) -> None:
        target = compiler.compile(mgr.Or(a, b))
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.count_truth_assignments() == 3

    def test_count_truth_assignments_true(self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor) -> None:
        target = compiler.compile(mgr.TRUE())
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.count_truth_assignments() > 0

    def test_clause_entails_trivial(self, engine: SddEngine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        assert engine.clause_entails(a)
        assert engine.clause_entails(b)
        assert engine.clause_entails(mgr.Or(a, b))

    def test_clause_entails_false_target(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode, b: FNode
    ) -> None:
        abstr.get_id(a)
        abstr.get_id(b)
        target = compiler.compile(mgr.FALSE())
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.clause_entails(a)
        assert engine.clause_entails(mgr.Not(a))
        assert engine.clause_entails(mgr.Or(a, b))

    def test_clause_entails_not_entailed(self, engine: SddEngine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        assert not engine.clause_entails(mgr.Not(a))
        assert not engine.clause_entails(mgr.Not(b))

    def test_clause_entails_tautology(self, engine: SddEngine, mgr: FormulaManager) -> None:
        assert engine.clause_entails(mgr.TRUE())

    def test_is_implicant_trivial(self, engine: SddEngine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        assert engine.is_implicant(mgr.And(a, b))
        assert not engine.is_implicant(a)
        assert not engine.is_implicant(b)

    def test_is_implicant_not_implicant(self, engine: SddEngine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        assert not engine.is_implicant(mgr.And(mgr.Not(a), b))
        assert not engine.is_implicant(mgr.Not(a))

    def test_is_implicant_or(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode, b: FNode
    ) -> None:
        target = compiler.compile(mgr.Or(a, b))
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.is_implicant(a)
        assert engine.is_implicant(b)
        assert engine.is_implicant(mgr.And(a, mgr.Not(b)))
        assert not engine.is_implicant(mgr.And(mgr.Not(a), mgr.Not(b)))

    def test_is_implicant_false_target(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode, b: FNode
    ) -> None:
        abstr.get_id(a)
        abstr.get_id(b)
        target = compiler.compile(mgr.FALSE())
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.is_implicant(mgr.And(a, mgr.Not(a)))
        assert engine.is_implicant(mgr.FALSE())

    def test_is_implicant_invalid_input(self, engine: SddEngine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        with pytest.raises(ValueError):
            engine.is_implicant(mgr.Or(a, b))

    def test_enumerate_truth_assignments_and(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode, b: FNode
    ) -> None:
        target = compiler.compile(mgr.And(a, b))
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 1
        assert assignments[0] == {a: True, b: True}

    def test_enumerate_truth_assignments_or(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode, b: FNode
    ) -> None:
        target = compiler.compile(mgr.Or(a, b))
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 3
        assert {a: True, b: True} in assignments
        assert {a: True, b: False} in assignments
        assert {a: False, b: True} in assignments

    def test_enumerate_truth_assignments_false(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor
    ) -> None:
        target = compiler.compile(mgr.FALSE())
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 0

    def test_enumerate_truth_assignments_theory(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor
    ) -> None:
        x = mgr.Symbol("x", INT)
        f1 = mgr.GT(x, mgr.Int(0))
        f2 = mgr.LE(x, mgr.Int(10))
        formula = mgr.And(f1, f2)
        target = compiler.compile(formula)
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assignments = list(engine.enumerate_truth_assignments())
        assert len(assignments) == 1
        assert assignments[0] == {f1: True, f2: True}

    def test_theory_atoms(self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor) -> None:
        x = mgr.Symbol("x", INT)
        f1 = mgr.GT(x, mgr.Int(0))
        f2 = mgr.LE(x, mgr.Int(10))
        formula = mgr.And(f1, f2)
        target = compiler.compile(formula)
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.is_satisfiable()
        assert engine.count_truth_assignments() == 1
        assert engine.clause_entails(f1)
        assert engine.clause_entails(f2)

    def test_multiple_queries(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode, b: FNode
    ) -> None:
        target = compiler.compile(mgr.Or(a, b))
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.is_satisfiable()
        assert engine.count_truth_assignments() == 3
        assert engine.clause_entails(mgr.Or(a, b))
        assert not engine.clause_entails(mgr.Or(mgr.Not(a), mgr.Not(b)))
