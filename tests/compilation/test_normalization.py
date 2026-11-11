"""Compilation canonicalizes formulas, lemmas, default projections, and explicit projection polarity."""

import pytest
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.typing import BOOL, INT

from tddnnf import TheoryCompilation
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.normalization.normalizer import NormalizerWalker


def test_context_derives_default_projection_from_normalized_formula(
    env: Environment, mgr: FormulaManager, x: FNode, p: FNode
) -> None:
    norm = NormalizerWalker(env)
    x_ge_2 = mgr.GE(x, mgr.Int(2))
    x_ge_2_equiv = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    phi = mgr.And(p, x_ge_2_equiv)

    context = TheoryCompilation(phi, env=env)

    assert context.phi == norm.normalize(phi)
    assert set(context.project_on) == {p, norm.normalize(x_ge_2)}


def test_context_makes_explicit_projection_atoms_positive(
    env: Environment, mgr: FormulaManager, x: FNode, p: FNode
) -> None:
    norm = NormalizerWalker(env)
    x_lt_two = mgr.LT(x, mgr.Int(2))

    context = TheoryCompilation(p, project_on=[x_lt_two], env=env)

    normalized = norm.normalize(x_lt_two)
    assert normalized.is_not()
    assert context.project_on == (normalized.arg(0),)


@pytest.mark.parametrize("strategy", ["treduced", "textended"])
def test_compilation_matches_normalized_construction(mgr: FormulaManager, strategy: str) -> None:
    x = mgr.Symbol(f"compilation_context_{strategy}_x", INT)
    p = mgr.Symbol(f"compilation_context_{strategy}_p", BOOL)
    raw_atom = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    raw_lemma = mgr.Or(mgr.Not(p), raw_atom)
    context = TheoryCompilation(p, project_on=[p, raw_atom], env=mgr.env)
    normalized_lemma = context.normalize(raw_lemma)
    with NormalizerWalker(mgr.env) as normalizer:
        assert normalized_lemma == normalizer.normalize(raw_lemma)

    with context:
        target = getattr(context, f"compile_{strategy}")(SddCompiler(), [raw_lemma])
        expected = (
            mgr.And(context.phi, normalized_lemma)
            if strategy == "treduced"
            else mgr.Or(context.phi, mgr.Not(normalized_lemma))
        )
    difference = mgr.Not(mgr.Iff(target.to_pysmt(), expected))
    with mgr.env.factory.Solver() as solver:
        solver.add_assertion(difference)
        assert not solver.solve()

    normalized_atom = target.projection_atoms[1]
    assert raw_atom != normalized_atom
    assert raw_atom not in target.abstr
    assert normalized_atom in target.abstr
    assert target.projection_atoms == (p, normalized_atom)
