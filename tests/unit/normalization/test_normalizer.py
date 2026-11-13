import pytest
from pysmt.environment import Environment, get_env
from pysmt.typing import INT, REAL

from tddnnf.normalization.normalizer import NormalizerWalker


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("shape", ["boolean", "integer", "real", "true", "false", "negated"])
def test_normalized_results_preserve_meaning_and_ownership(env, assert_owned_dag, shape, explicit):
    destination = Environment() if explicit else env
    mgr = destination.formula_manager
    p = mgr.Symbol("p")
    atom = mgr.GE(mgr.Times(mgr.Int(2), mgr.Symbol("n", INT)), mgr.Int(4))
    phi = {
        "boolean": mgr.And(p, mgr.Not(p)),
        "integer": atom,
        "real": mgr.LE(mgr.Times(mgr.Real(2), mgr.Symbol("x", REAL)), mgr.Real(4)),
        "true": mgr.TRUE(),
        "false": mgr.FALSE(),
        "negated": mgr.Not(atom),
    }[shape]
    with NormalizerWalker(destination if explicit else None) as normalizer:
        result = normalizer.normalize(phi)
        assert_owned_dag(result, destination)
        assert normalizer.normalize(result) is result
        with destination.factory.Solver(name="msat") as solver:
            solver.add_assertion(mgr.Not(mgr.Iff(result, phi)))
            assert not solver.solve()
        if shape in ("boolean", "true", "false"):
            assert result is phi
    assert get_env() is env


def test_equivalent_arithmetic_atoms_have_one_owned_canonical_form(env, assert_owned_dag):
    mgr = env.formula_manager
    n = mgr.Symbol("n", INT)
    with NormalizerWalker(env) as normalizer:
        first = normalizer.normalize(mgr.GE(n, mgr.Int(2)))
        second = normalizer.normalize(mgr.GE(mgr.Times(mgr.Int(2), n), mgr.Int(4)))
        assert first is second
        assert_owned_dag(first, env)
        assert_owned_dag(second, env)


@pytest.mark.parametrize("entry", ["walk", "normalize"])
def test_rejects_foreign_inputs(env, entry):
    mgr = env.formula_manager
    local = mgr.Symbol("p")
    foreign = Environment().formula_manager.Symbol("p")
    assert foreign is not local
    with NormalizerWalker(env) as normalizer:
        with pytest.raises(AssertionError, match="selected environment"):
            getattr(normalizer, entry)(foreign)


def test_context_returns_same_instance_and_closes_on_normal_exit(env):
    normalizer = NormalizerWalker(env)
    with normalizer as entered:
        assert entered is normalizer

    with pytest.raises(RuntimeError):
        normalizer.normalize(env.formula_manager.Symbol("p"))


def test_context_propagates_exception_and_closes(env):
    normalizer = NormalizerWalker(env)
    error = ValueError("context body failed")

    with pytest.raises(ValueError) as caught:
        with normalizer:
            raise error

    assert caught.value is error
    with pytest.raises(RuntimeError):
        normalizer.normalize(env.formula_manager.Symbol("p"))


def test_close_is_idempotent(env):
    normalizer = NormalizerWalker(env)
    normalizer.close()
    normalizer.close()


def test_closed_normalizer_rejects_cached_input_and_context_entry(env):
    symbol = env.formula_manager.Symbol("p")
    normalizer = NormalizerWalker(env)
    assert normalizer.normalize(symbol) is symbol
    normalizer.close()

    with pytest.raises(RuntimeError):
        normalizer.walk(symbol)
    with pytest.raises(RuntimeError):
        normalizer.normalize(symbol)
    with pytest.raises(RuntimeError):
        with normalizer:
            pass
