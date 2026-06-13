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

    def test_model_count_and(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode, b: FNode
    ) -> None:
        target = compiler.compile(mgr.And(a, b))
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.model_count() == 1

    def test_model_count_or(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode, b: FNode
    ) -> None:
        target = compiler.compile(mgr.Or(a, b))
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.model_count() == 3

    def test_model_count_true(self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor) -> None:
        target = compiler.compile(mgr.TRUE())
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.model_count() > 0

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

    def test_theory_atoms(self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor) -> None:
        x = mgr.Symbol("x", INT)
        f1 = mgr.GT(x, mgr.Int(0))
        f2 = mgr.LE(x, mgr.Int(10))
        formula = mgr.And(f1, f2)
        target = compiler.compile(formula)
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.is_satisfiable()
        assert engine.model_count() == 1
        assert engine.clause_entails(f1)
        assert engine.clause_entails(f2)

    def test_multiple_queries(
        self, mgr: FormulaManager, compiler: SddCompiler, abstr: Abstractor, a: FNode, b: FNode
    ) -> None:
        target = compiler.compile(mgr.Or(a, b))
        engine = SddEngine(TheoryCompiledTarget(target, abstr))
        assert engine.is_satisfiable()
        assert engine.model_count() == 3
        assert engine.clause_entails(mgr.Or(a, b))
        assert not engine.clause_entails(mgr.Or(mgr.Not(a), mgr.Not(b)))
