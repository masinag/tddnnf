"""Native and absent dimensions, sparse IDs, projection order, and constant circuits."""

import ddnnife
import pytest

from tddnnf import TheoryCompilation
from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.compilers.pysdd import SddCompiledTarget
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries import DdnnifeEngine
from tests.support import PAIRINGS


@pytest.mark.parametrize("sparse", [False, True])
@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("shape", ["true", "false", "atom"])
def test_projected_enumeration(mgr, a, b, c, compiler, engine_factory, sparse, project, shape):
    abstr = Abstractor({3: a, 7: b, 11: c} if sparse else {1: a, 2: b, 3: c})
    projection = [b, a] if project else []
    formula = {"true": c, "false": mgr.FALSE(), "atom": mgr.And(a, c)}[shape]
    native = compiler.compile(formula, abstr, project_on=projection)
    target = TheoryCompiledTarget(native, abstr, projection, env=mgr.env)
    if isinstance(native, D4CompiledTarget) and native.nnf_text in ("t 1\n", "f 1\n"):
        with pytest.raises(ddnnife.InternalError):
            engine_factory(target)
        return
    engine = engine_factory(target)
    expected = []
    if shape != "false":
        expected = (
            [
                {a: value, b: unused}
                for value in ([False, True] if shape == "true" else [True])
                for unused in [False, True]
            ]
            if project
            else [{}]
        )
    models = list(engine.enumerate_truth_assignments())
    assert {frozenset(model.items()) for model in models} == {frozenset(model.items()) for model in expected}
    assert len(models) == len(expected) == engine.count_truth_assignments()


@pytest.mark.parametrize("sparse", [False, True])
@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("shape", ["true", "false", "atom"])
def test_count_uses_native_dimensions(mgr, compiler, engine_factory, sparse, project, shape):
    a = mgr.Symbol("a")
    abstr = Abstractor({7: a}) if sparse else Abstractor()
    formula = {"true": mgr.TRUE(), "false": mgr.FALSE(), "atom": a}[shape]
    projection = [a] if project else []
    with TheoryCompilation(formula, projection, env=mgr.env) as compilation:
        target = compilation.compile_treduced(compiler, [], abstractor=abstr)
    if isinstance(target.target, D4CompiledTarget) and target.target.nnf_text in ("t 1\n", "f 1\n"):
        with pytest.raises(ddnnife.InternalError):
            engine_factory(target)
        return
    engine = engine_factory(target)
    expected = 0 if shape == "false" else (2 if project and shape == "true" else 1)
    assert engine.count_truth_assignments() == expected
    if project:
        assert engine.count_truth_assignments([a]) == (0 if shape == "false" else 1)
        assert engine.count_truth_assignments([mgr.Not(a)]) == (1 if shape == "true" else 0)


@pytest.mark.parametrize("reverse", [False, True])
def test_enumeration_projection_order(mgr, compiler, a, b, reverse, engine_factory):
    projection = [b, a] if reverse else [a, b]
    abstr = Abstractor({1: a, 2: b})
    native = compiler.compile(mgr.Or(a, b), abstr, project_on=projection)
    engine = engine_factory(TheoryCompiledTarget(native, abstr, projection, env=mgr.env))
    models = list(engine.enumerate_truth_assignments())
    assert len(models) == 3
    assert all(tuple(model) == tuple(projection) for model in models)


@pytest.mark.parametrize("pairing", PAIRINGS[1:])
def test_rejects_missing_projection_mapping(mgr, a, b, compiler, pairing, engine_factory):
    abstr = Abstractor({3: a, 7: b})
    native = compiler.compile(a, abstr, project_on=[a, b])
    mapping = {3: native.remapping[3]}
    if isinstance(native, SddCompiledTarget):
        native = SddCompiledTarget(native.root, native.manager, mapping)
    else:
        native = D4CompiledTarget(native.nnf_text, native.var_count, mapping)
    container = TheoryCompiledTarget(native, abstr, [a, b], env=mgr.env)
    with pytest.raises(AssertionError, match="mapping must cover the projection"):
        engine_factory(container)


def test_absent_projection_atom(mgr, a, b, compiler, engine_factory):
    abstr = Abstractor({3: a, 7: b})
    native = compiler.compile(a, abstr, project_on=[a, b])
    engine = engine_factory(TheoryCompiledTarget(native, abstr, [a, b], env=mgr.env))
    models = list(engine.enumerate_truth_assignments())
    assert len(models) == 2
    assert {frozenset(m.items()) for m in models} == {
        frozenset({a: True, b: True}.items()),
        frozenset({a: True, b: False}.items()),
    }
    assert engine.count_truth_assignments() == 2
    for assumption in (b, mgr.Not(b)):
        assert engine.is_satisfiable([assumption])
        assert engine.count_truth_assignments([assumption]) == 1
    assert not engine.is_satisfiable([b, mgr.Not(b)])
    assert engine.count_truth_assignments([b, mgr.Not(b)]) == 0


@pytest.mark.parametrize("truth", [False, True])
@pytest.mark.parametrize("active", [False, True])
def test_constant_targets(mgr, a, compiler, pairing, engine_factory, truth, active):
    projection = [a] if active else []
    abstr = Abstractor({1: a})
    native = compiler.compile(mgr.Bool(truth), abstr, project_on=projection)
    container = TheoryCompiledTarget(native, abstr, projection, env=mgr.env)
    if pairing[1] is DdnnifeEngine and (not truth or not active):
        with pytest.raises(ddnnife.InternalError):
            engine_factory(container)
        return
    engine = engine_factory(container)
    assert engine.is_satisfiable() == truth
    assert engine.is_valid() == truth
    assert engine.count_truth_assignments() == (2 ** len(projection) if truth else 0)
    if active:
        assert engine.count_truth_assignments([a]) == int(truth)
    assert engine.entails_clause([mgr.TRUE()])
    assert engine.entails_clause([]) == (not truth)
    assert engine.is_implicant([mgr.TRUE()]) == truth
    assert engine.is_implicant([mgr.FALSE()])
    models = list(engine.enumerate_truth_assignments())
    expected = [{a: True}, {a: False}] if active else [{}]
    if not truth:
        expected = []
    assert len(models) == len(expected)
    assert {frozenset(m.items()) for m in models} == {frozenset(m.items()) for m in expected}
