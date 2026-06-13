import tempfile
from pathlib import Path

import pytest
from pysmt.typing import INT

from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler


class TestSddCompiler:
    @pytest.fixture
    def compiler(self, ctx, env) -> SddCompiler:
        return SddCompiler(ctx, env=env)

    def test_and(self, mgr, compiler, a, b) -> None:
        target = compiler.compile(mgr.And(a, b))
        assert target.root.model_count() == 1

    def test_or(self, mgr, compiler, a, b) -> None:
        target = compiler.compile(mgr.Or(a, b))
        assert target.root.model_count() == 3

    def test_not(self, mgr, compiler, a) -> None:
        target = compiler.compile(mgr.Not(a))
        assert target.root.model_count() == 1

    def test_nested(self, mgr, compiler, a, b, c) -> None:
        target = compiler.compile(mgr.And(mgr.Or(a, b), mgr.Not(c)))
        assert target.root.model_count() == 3

    def test_implies(self, mgr, compiler, a, b) -> None:
        target = compiler.compile(mgr.Implies(a, b))
        assert target.root.model_count() == 3

    def test_iff(self, mgr, compiler, a, b) -> None:
        target = compiler.compile(mgr.Iff(a, b))
        assert target.root.model_count() == 2

    def test_ite(self, mgr, compiler, a, b, c) -> None:
        target = compiler.compile(mgr.Ite(a, b, c))
        assert target.root.model_count() == 4

    def test_true(self, mgr, compiler) -> None:
        target = compiler.compile(mgr.TRUE())
        assert target.root.is_true()

    def test_false(self, mgr, compiler) -> None:
        target = compiler.compile(mgr.FALSE())
        assert target.root.is_false()

    def test_save_load_roundtrip(self, mgr, compiler, a, b) -> None:
        target = compiler.compile(mgr.And(a, b))
        original_mc = target.root.model_count()

        with tempfile.TemporaryDirectory() as tmpdir:
            target.save(Path(tmpdir))
            loaded = SddCompiledTarget.load(Path(tmpdir))
            assert loaded.root.model_count() == original_mc

    def test_smt_formula_with_theory_atoms(self, mgr, compiler) -> None:
        x = mgr.Symbol("x", INT)
        f1 = mgr.GT(x, mgr.Int(0))
        f2 = mgr.GT(x, mgr.Int(1))
        smt_formula = mgr.And(f1, f2)

        target = compiler.compile(smt_formula)
        assert target.root.model_count() == 1

    def test_mixed_bool_and_theory(self, mgr, compiler, a) -> None:
        x = mgr.Symbol("x", INT)
        f1 = mgr.GT(x, mgr.Int(0))
        f2 = mgr.LE(x, mgr.Int(10))
        formula = mgr.And(mgr.Or(a, f1), f2)

        target = compiler.compile(formula)
        assert target.root.model_count() == 3
