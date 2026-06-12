import pytest
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf.core.abstraction import AbstractionContext


class TestAbstractionContext:
    def test_to_dict_keys_are_full_smtlib_scripts(self, mgr: FormulaManager, x: FNode, ctx: AbstractionContext) -> None:
        ctx.get_bool(mgr.GT(x, mgr.Int(5)))

        data = ctx.to_dict()
        key = next(iter(data))
        assert key.startswith("(set-log")
        assert "(declare-fun" in key
        assert "(assert" in key
        assert "(check-sat)" in key

    def test_round_trip_preserves_identity(
        self, env: Environment, mgr: FormulaManager, x: FNode, p: FNode, ctx: AbstractionContext
    ) -> None:
        a1 = ctx.get_bool(mgr.GT(x, mgr.Int(0)))
        a2 = ctx.get_bool(p)
        a3 = ctx.get_bool(mgr.GT(x, mgr.Int(1)))

        data = ctx.to_dict()
        ctx2 = AbstractionContext.from_dict(data, env)

        assert ctx2.get_smt(a1) is ctx.get_smt(a1)
        assert ctx2.get_smt(a2) is ctx.get_smt(a2)
        assert ctx2.get_smt(a3) is ctx.get_smt(a3)
        assert ctx2.to_dict() == data

    def test_mixed_theory_types(
        self, env: Environment, mgr: FormulaManager, x: FNode, y_real: FNode, p: FNode, ctx: AbstractionContext
    ) -> None:
        a1 = ctx.get_bool(mgr.GT(x, mgr.Int(3)))
        a2 = ctx.get_bool(mgr.GE(y_real, mgr.Real(1.5)))
        a3 = ctx.get_bool(p)

        data = ctx.to_dict()
        ctx2 = AbstractionContext.from_dict(data, env)

        assert ctx2.get_smt(a1) is ctx.get_smt(a1)
        assert ctx2.get_smt(a2) is ctx.get_smt(a2)
        assert ctx2.get_smt(a3) is ctx.get_smt(a3)

    def test_abstraction_works_after_round_trip(
        self, env: Environment, mgr: FormulaManager, x: FNode, y_int: FNode, ctx: AbstractionContext
    ) -> None:
        a = mgr.GT(x, mgr.Int(0))
        b = mgr.GT(y_int, mgr.Int(0))
        ctx.get_bool(a)
        ctx.get_bool(b)

        data = ctx.to_dict()
        ctx2 = AbstractionContext.from_dict(data, env)

        formula = mgr.And(a, b)
        abstracted = ctx2.abstract(formula)
        assert abstracted.is_and()
        assert len(abstracted.args()) == 2
        assert abstracted.args()[0].is_symbol()
        assert abstracted.args()[1].is_symbol()

    def test_get_bool_adds_new_atoms(self, mgr: FormulaManager, x: FNode, ctx: AbstractionContext) -> None:
        a = mgr.GT(x, mgr.Int(0))
        b = mgr.GT(x, mgr.Int(1))

        idx1 = ctx.get_bool(a)
        idx2 = ctx.get_bool(b)
        idx3 = ctx.get_bool(a)

        assert idx1 == 1
        assert idx2 == 2
        assert idx3 == 1

    def test_get_smt_rejects_negative(self, mgr: FormulaManager, x: FNode, ctx: AbstractionContext) -> None:
        idx = ctx.get_bool(mgr.GT(x, mgr.Int(0)))
        with pytest.raises(ValueError, match="positive"):
            ctx.get_smt(-idx)

    def test_get_smt_rejects_zero(self, mgr: FormulaManager, x: FNode, ctx: AbstractionContext) -> None:
        ctx.get_bool(mgr.GT(x, mgr.Int(0)))
        with pytest.raises(ValueError, match="positive"):
            ctx.get_smt(0)
