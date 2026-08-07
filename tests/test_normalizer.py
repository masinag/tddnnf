from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf import KCMTContext
from tddnnf.normalization.normalizer import NormalizerWalker


def test_normalizer_canonicalizes_equivalent_atoms(
    env: Environment, mgr: FormulaManager, x: FNode, y_int: FNode, p: FNode
) -> None:
    norm = NormalizerWalker(env)

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
    norm = NormalizerWalker(env)

    phi: FNode = mgr.And(p, mgr.Not(p))
    normal = norm.normalize(phi)

    assert normal == phi


def test_normalizer_handles_no_theory_atoms(env: Environment, mgr: FormulaManager) -> None:
    norm = NormalizerWalker(env)

    t = mgr.TRUE()
    f = mgr.FALSE()
    phi: FNode = mgr.And(t, mgr.Not(f))

    normal = norm.normalize(phi)
    assert normal == phi


def test_context_normalizes_formula(env: Environment, mgr: FormulaManager, x: FNode, p: FNode) -> None:
    norm = NormalizerWalker(env)
    x_ge_2_equiv = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    phi = mgr.And(p, x_ge_2_equiv)

    context = KCMTContext(phi, normalizer=norm)

    assert context.phi == norm.normalize(phi)


def test_context_derives_default_projection_from_normalized_formula(
    env: Environment, mgr: FormulaManager, x: FNode, p: FNode
) -> None:
    norm = NormalizerWalker(env)
    x_ge_2 = mgr.GE(x, mgr.Int(2))
    x_ge_2_equiv = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    phi = mgr.And(p, x_ge_2_equiv)

    context = KCMTContext(phi, normalizer=norm)

    assert set(context.project_on or []) == {p, norm.normalize(x_ge_2)}


def test_context_normalizes_explicit_projection_atoms(
    env: Environment, mgr: FormulaManager, x: FNode, p: FNode
) -> None:
    norm = NormalizerWalker(env)
    x_ge_2 = mgr.GE(x, mgr.Int(2))
    x_ge_2_equiv = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    phi = mgr.And(p, x_ge_2_equiv)

    context = KCMTContext(phi, project_on=[x_ge_2_equiv], normalizer=norm)

    assert context.project_on == [norm.normalize(x_ge_2)]


def test_context_normalizes_external_lemma(env: Environment, mgr: FormulaManager, x: FNode, p: FNode) -> None:
    norm = NormalizerWalker(env)
    x_ge_2_equiv = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    lemma = mgr.Or(p, mgr.Not(x_ge_2_equiv))
    context = KCMTContext(normalizer=norm)

    assert context.normalize(lemma) == norm.normalize(lemma)
