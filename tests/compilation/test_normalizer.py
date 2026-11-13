"""The normalizer canonicalizes equivalent theory atoms and preserves Boolean structure."""

import pytest
from pysmt.environment import Environment
from pysmt.exceptions import UnsupportedOperatorError
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.typing import INT

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.normalization.normalizer import NormalizerWalker
from tests.support import STRATEGIES


def test_normalizer_canonicalizes_equivalent_atoms(
    env: Environment, mgr: FormulaManager, x: FNode, y_int: FNode, p: FNode
) -> None:
    with NormalizerWalker(env) as norm:
        y_le_x: FNode = mgr.LE(y_int, x)
        x_le_y: FNode = mgr.LE(x, y_int)
        x_le_y_equiv: FNode = mgr.LE(mgr.Plus(x, mgr.Times(mgr.Int(-1), y_int)), mgr.Int(0))
        x_ge_2: FNode = mgr.GE(x, mgr.Int(2))
        x_ge_2_equiv: FNode = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))

        x_le_y_norm = norm.normalize(x_le_y)
        assert x_le_y_norm == norm.normalize(x_le_y_equiv)
        x_ge_2_norm = norm.normalize(x_ge_2)
        assert x_ge_2_norm == norm.normalize(x_ge_2_equiv)

        phi: FNode = mgr.And(
            p,
            mgr.Or(x_le_y, mgr.Not(y_le_x)),
            mgr.And(x_le_y_equiv, x_ge_2),
            x_ge_2_equiv,
        )

        normal = norm.normalize(phi)

        expected: FNode = mgr.And(
            p,
            mgr.Or(x_le_y_norm, mgr.Not(y_le_x)),
            mgr.And(x_le_y_norm, x_ge_2_norm),
            x_ge_2_norm,
        )
        assert normal == expected


def test_normalizer_preserves_pure_boolean(env: Environment, mgr: FormulaManager, p: FNode) -> None:
    with NormalizerWalker(env) as norm:
        phi: FNode = mgr.And(p, mgr.Not(p))
        normal = norm.normalize(phi)

        assert normal == phi


def test_normalizer_handles_no_theory_atoms(env: Environment, mgr: FormulaManager) -> None:
    with NormalizerWalker(env) as norm:
        t = mgr.TRUE()
        f = mgr.FALSE()
        phi: FNode = mgr.And(t, mgr.Not(f))

        normal = norm.normalize(phi)
        assert normal == phi


def test_normalizer_lifecycle(mgr):
    session = NormalizerWalker(mgr.env)
    with pytest.raises(LookupError), session:
        raise LookupError("body failure")
    session.close()
    with pytest.raises(RuntimeError, match="closed"):
        session.normalize(mgr.TRUE())
    with pytest.raises(RuntimeError, match="closed"):
        session.__enter__()


@pytest.mark.parametrize("kind", ["forall", "exists"])
@pytest.mark.parametrize("position", ["formula", "lemma"])
def test_normalizer_rejects_quantified_inputs(mgr, kind, position):
    x = mgr.Symbol("x", INT)
    quantified = getattr(mgr, "ForAll" if kind == "forall" else "Exists")([x], mgr.GE(x, mgr.Int(0)))
    if position == "formula":
        with pytest.raises(UnsupportedOperatorError):
            TheoryCompilation(quantified, env=mgr.env)
    else:
        with TheoryCompilation(mgr.TRUE(), env=mgr.env) as compilation:
            for strategy in STRATEGIES:
                with pytest.raises(UnsupportedOperatorError):
                    getattr(compilation, strategy)(BddCompiler(), [quantified])
