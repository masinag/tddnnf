from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.shortcuts import is_valid
from pysmt.typing import INT

from tddnnf.core.interfaces import PropCompiledTarget, PropCompiler


class BaseTestCompiler:
    compiler_cls: type[PropCompiler]
    target_cls: type[PropCompiledTarget]

    @pytest.fixture
    def compiler(self, abstr) -> PropCompiler:
        return self.compiler_cls(abstr)

    def _count(self, target) -> int:
        raise NotImplementedError

    def _is_true(self, target) -> bool:
        raise NotImplementedError

    def _is_false(self, target) -> bool:
        raise NotImplementedError

    def test_and(self, mgr: FormulaManager, compiler, a: FNode, b: FNode) -> None:
        target = compiler.compile(mgr.And(a, b))
        assert self._count(target) == 1

    def test_or(self, mgr: FormulaManager, compiler, a: FNode, b: FNode) -> None:
        target = compiler.compile(mgr.Or(a, b))
        assert self._count(target) == 3

    def test_not(self, mgr: FormulaManager, compiler, a: FNode) -> None:
        target = compiler.compile(mgr.Not(a))
        assert self._count(target) == 1

    def test_nested(self, mgr: FormulaManager, compiler, a: FNode, b: FNode, c: FNode) -> None:
        target = compiler.compile(mgr.And(mgr.Or(a, b), mgr.Not(c)))
        assert self._count(target) == 3

    def test_implies(self, mgr: FormulaManager, compiler, a: FNode, b: FNode) -> None:
        target = compiler.compile(mgr.Implies(a, b))
        assert self._count(target) == 3

    def test_iff(self, mgr: FormulaManager, compiler, a: FNode, b: FNode) -> None:
        target = compiler.compile(mgr.Iff(a, b))
        assert self._count(target) == 2

    def test_ite(self, mgr: FormulaManager, compiler, a: FNode, b: FNode, c: FNode) -> None:
        target = compiler.compile(mgr.Ite(a, b, c))
        assert self._count(target) == 4

    def test_true(self, mgr: FormulaManager, compiler) -> None:
        target = compiler.compile(mgr.TRUE())
        assert self._is_true(target)

    def test_false(self, mgr: FormulaManager, compiler) -> None:
        target = compiler.compile(mgr.FALSE())
        assert self._is_false(target)

    def test_save_load_roundtrip(self, mgr: FormulaManager, compiler, a: FNode, b: FNode) -> None:
        target = compiler.compile(mgr.And(a, b))
        original_mc = self._count(target)

        with tempfile.TemporaryDirectory() as tmpdir:
            target.save(Path(tmpdir))
            loaded = self.target_cls.load(Path(tmpdir))
            assert self._count(loaded) == original_mc

    def test_smt_formula_with_theory_atoms(self, mgr: FormulaManager, compiler) -> None:
        x = mgr.Symbol("x", INT)
        f1 = mgr.GT(x, mgr.Int(0))
        f2 = mgr.GT(x, mgr.Int(1))
        smt_formula = mgr.And(f1, f2)

        target = compiler.compile(smt_formula)
        assert self._count(target) == 1

    def test_mixed_bool_and_theory(self, mgr: FormulaManager, compiler, a: FNode) -> None:
        x = mgr.Symbol("x", INT)
        f1 = mgr.GT(x, mgr.Int(0))
        f2 = mgr.LE(x, mgr.Int(10))
        formula = mgr.And(mgr.Or(a, f1), f2)

        target = compiler.compile(formula)
        assert self._count(target) == 3

    def test_projected_no_atoms_left_tautology(self, mgr: FormulaManager, compiler, a: FNode) -> None:
        formula = a
        target = compiler.compile(formula, project_on=[])
        assert self._is_true(target)

    def test_projected_forget_one(self, mgr: FormulaManager, compiler, a: FNode, b: FNode) -> None:
        formula = mgr.And(a, b)
        target = compiler.compile(formula, project_on=[a])
        assert not self._is_true(target)
        assert not self._is_false(target)

    def test_projected_forget_all_contradiction(self, mgr: FormulaManager, compiler, a: FNode) -> None:
        formula = mgr.And(a, mgr.Not(a))
        target = compiler.compile(formula, project_on=[])
        assert self._is_false(target)

    def test_to_pysmt(self, mgr, compiler, abstr, a, b, c) -> None:
        phi = mgr.And(mgr.Or(a, b), mgr.Not(c))
        target = compiler.compile(phi)
        reconstructed = target.to_pysmt(abstr, mgr)
        assert is_valid(mgr.Iff(phi, reconstructed))

    def test_to_pysmt_true(self, mgr, compiler, abstr) -> None:
        target = compiler.compile(mgr.TRUE())
        reconstructed = target.to_pysmt(abstr, mgr)
        assert is_valid(mgr.Iff(mgr.TRUE(), reconstructed))

    def test_to_pysmt_false(self, mgr, compiler, abstr) -> None:
        target = compiler.compile(mgr.FALSE())
        reconstructed = target.to_pysmt(abstr, mgr)
        assert is_valid(mgr.Iff(mgr.FALSE(), reconstructed))

    def test_to_pysmt_theory_atoms(self, mgr, compiler, abstr, x) -> None:
        f1 = mgr.GT(x, mgr.Int(0))
        f2 = mgr.LT(x, mgr.Int(10))
        phi = mgr.And(f1, f2)
        target = compiler.compile(phi)
        reconstructed = target.to_pysmt(abstr, mgr)
        assert is_valid(mgr.Iff(phi, reconstructed))

    def test_to_pysmt_mixed_bool_theory(self, mgr, compiler, abstr, a, x) -> None:
        f1 = mgr.GT(x, mgr.Int(0))
        phi = mgr.Or(a, f1)
        target = compiler.compile(phi)
        reconstructed = target.to_pysmt(abstr, mgr)
        assert is_valid(mgr.Iff(phi, reconstructed))
