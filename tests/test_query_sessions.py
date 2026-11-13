from itertools import product
from pathlib import Path
from unittest.mock import Mock

import ddnnife
import pytest
from pysmt.environment import Environment, pop_env, push_env
from pysmt.typing import BOOL, INT

import tddnnf.queries.ddnnife_engine as ddnnife_module
from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiledTarget, BddCompiler
from tddnnf.compilers.d4 import D4CompiledTarget, D4Compiler
from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries import BddEngine, DdnnifeEngine, SddEngine
from tddnnf.queries.session import QuerySession
from tests._base_engine_test import BaseTestEngine

PAIRINGS = [(BddCompiler, BddEngine), (SddCompiler, SddEngine), (D4Compiler, DdnnifeEngine)]


def open_queries(target):
    engine_type = {BddCompiledTarget: BddEngine, SddCompiledTarget: SddEngine, D4CompiledTarget: DdnnifeEngine}
    return target.queries(engine_type[type(target.target)])


class TestCuddSessions(BaseTestEngine):
    compiler_cls = BddCompiler
    engine_cls = staticmethod(open_queries)


class TestSddSessions(BaseTestEngine):
    compiler_cls = SddCompiler
    engine_cls = staticmethod(open_queries)


class TestDdnnifeSessions(BaseTestEngine):
    compiler_cls = D4Compiler
    engine_cls = staticmethod(open_queries)


@pytest.fixture(params=PAIRINGS, ids=["cudd", "sdd", "ddnnife"])
def pairing(request):
    return request.param


def compile_target(mgr, pairing, formula, atoms):
    with TheoryCompilation(formula, all_vars=atoms, env=mgr.env) as compilation:
        return compilation.compile_treduced(pairing[0](), [])


def test_literals_constants_and_validation(mgr, a, b, c, pairing):
    target = compile_target(mgr, pairing, mgr.Or(a, b), [b, a])
    original_ids = dict(target.abstr.atom_to_id)
    with target.queries(pairing[1]) as q:
        assert q.is_satisfiable([])
        assert q.count_truth_assignments([a, a, mgr.TRUE()]) == 2
        assert not q.is_satisfiable([a, mgr.Not(a)])
        assert q.count_truth_assignments([a, mgr.Not(a)]) == 0
        assert not q.is_satisfiable([mgr.FALSE()])
        assert q.count_truth_assignments([mgr.Not(mgr.TRUE())]) == 0
        assert q.entails_clause(mgr.Or(a, mgr.Not(a)))
        assert q.is_implicant(mgr.And(a, mgr.Not(a)))
        assert q.entails_clause(mgr.TRUE())
        assert not q.entails_clause(mgr.FALSE())
        assert q.is_implicant(mgr.FALSE())
        assert not q.is_implicant(mgr.TRUE())
        assert not q.is_valid()
        assert q.is_implicant(a)
        assert all(tuple(m) == target.projection_atoms for m in q.enumerate_truth_assignments())
        for assumptions in ([a, mgr.Not(a), c], [mgr.FALSE(), c], [mgr.And(a, b)], [42]):
            for operation in (q.is_satisfiable, q.count_truth_assignments):
                with pytest.raises(ValueError):
                    operation(assumptions)
        for operation, formula in (
            (q.entails_clause, mgr.Or(mgr.TRUE(), mgr.Or(a, c))),
            (q.entails_clause, mgr.Or(a, mgr.Or(mgr.Not(a), c))),
            (q.entails_clause, mgr.Or(a, mgr.And(a, b))),
            (q.is_implicant, mgr.And(mgr.FALSE(), mgr.And(a, c))),
            (q.is_implicant, mgr.And(a, mgr.And(mgr.Not(a), c))),
            (q.is_implicant, mgr.And(a, mgr.Or(a, b))),
        ):
            with pytest.raises(ValueError):
                operation(formula)
        assert dict(target.abstr.atom_to_id) == original_ids


@pytest.mark.parametrize("truth,active", list(product([False, True], [False, True])))
def test_constant_targets(mgr, a, pairing, truth, active):
    target = compile_target(mgr, pairing, mgr.Bool(truth), [a] if active else [])
    if pairing[1] is DdnnifeEngine and (not truth or not active):
        with pytest.raises(ddnnife.InternalError):
            target.queries(pairing[1])
        return
    with target.queries(pairing[1]) as q:
        assert q.is_satisfiable() == truth
        assert q.is_valid() == truth
        assert q.count_truth_assignments() == (2 ** len(target.projection_atoms) if truth else 0)
        assert len(list(q.enumerate_truth_assignments())) == q.count_truth_assignments()
        assert q.entails_clause(mgr.FALSE()) == (not truth)
        assert q.is_implicant(mgr.TRUE()) == truth
        if active:
            assert q.count_truth_assignments([a]) == int(truth)


def test_sparse_projection_growth(mgr, a, b, c, pairing):
    forgotten = mgr.Symbol("forgotten", BOOL)
    abstr = Abstractor({3: a, 7: b, 11: c, 15: forgotten})
    native = pairing[0]().compile(mgr.And(a, forgotten), abstr, all_vars=[c, b, a, forgotten], exists_vars=[forgotten])
    target = TheoryCompiledTarget(native, abstr, [c, b, a], env=mgr.env)
    with target.queries(pairing[1]) as q:
        abstr.get_id(mgr.Symbol("later", BOOL))
        assert q.count_truth_assignments() == 4
        assert q.count_truth_assignments([c, c]) == 2
        assert q.count_truth_assignments([mgr.Not(a)]) == 0
        models = list(q.enumerate_truth_assignments())
        assert len(models) == len({frozenset(m.items()) for m in models}) == 4
        assert all(tuple(m) == (c, b, a) for m in models)
        with pytest.raises(ValueError):
            q.is_satisfiable([forgotten])


@pytest.mark.parametrize("pairing", PAIRINGS[:2], ids=["cudd", "sdd"])
@pytest.mark.parametrize("sparse", [False, True])
@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("shape", ["true", "false", "atom"])
def test_projected_enumeration(mgr, a, b, c, pairing, sparse, project, shape):
    abstr = Abstractor({3: a, 7: b, 11: c} if sparse else {1: a, 2: b, 3: c})
    projection = [b, a] if project else []
    formula = {"true": c, "false": mgr.FALSE(), "atom": mgr.And(a, c)}[shape]
    native = pairing[0]().compile(
        formula,
        abstr,
        all_vars=tuple(abstr.atom_to_id),
        exists_vars=[atom for atom in abstr.atom_to_id if atom not in projection],
    )
    target = TheoryCompiledTarget(native, abstr, projection, env=mgr.env)
    engine = pairing[1](target)
    root = native.root
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
    assert native.root is root


def test_equivalent_syntax_polarity_and_ambiguity(mgr, pairing, monkeypatch):
    x, y = mgr.Symbol("session_x", INT), mgr.Symbol("session_y", INT)
    atom = mgr.LE(y, x)
    opposite = mgr.LT(x, y)
    scaled = mgr.LE(mgr.Times(mgr.Int(2), y), mgr.Times(mgr.Int(2), x))
    abstr = Abstractor({1: atom})
    native = pairing[0]().compile(atom, abstr, all_vars=[atom])
    target = TheoryCompiledTarget(native, abstr, [atom], env=mgr.env)
    with target.queries(pairing[1]) as q:
        assert q.is_satisfiable([scaled])
        assert not q.is_satisfiable([opposite])
        assert q.count_truth_assignments([atom, opposite]) == 0
        assert q.entails_clause(scaled)
        assert q.is_implicant(mgr.Not(opposite))
        assert list(q.enumerate_truth_assignments()) == [{atom: True}]
        for operation, formula, expected in (
            ("entails_clause", mgr.Or(scaled, opposite), [atom, mgr.Not(atom)]),
            ("is_implicant", mgr.And(scaled, mgr.Not(opposite)), [atom, atom]),
        ):
            delegate = Mock(return_value=True)
            monkeypatch.setattr(q._inner, operation, delegate)
            assert getattr(q, operation)(formula)
            delegate.assert_called_once_with(expected)
    ambiguous = TheoryCompiledTarget(native, abstr, [atom, opposite], env=mgr.env)
    with pytest.raises(ValueError, match="Ambiguous"):
        ambiguous.queries(pairing[1])


def test_lifecycle_and_independence(mgr, a, b, pairing):
    target = compile_target(mgr, pairing, mgr.Or(a, b), [a, b])
    first = target.queries(pairing[1])
    second = target.queries(pairing[1])
    iterator = first.enumerate_truth_assignments()
    next(iterator)
    tmpdir = getattr(first._inner, "_tmpdir", None)
    path = Path(tmpdir.name) if tmpdir else None
    first.close()
    first.close()
    if path:
        assert not path.exists()
    for operation in (
        first.is_satisfiable,
        first.count_truth_assignments,
        first.is_valid,
        first.enumerate_truth_assignments,
        lambda: first.entails_clause(a),
        lambda: first.is_implicant(a),
    ):
        with pytest.raises(RuntimeError, match="closed"):
            operation()
    with pytest.raises(StopIteration):
        next(iterator)
    assert second.count_truth_assignments() == 3
    second.close()
    with pytest.raises(ZeroDivisionError):
        with target.queries(pairing[1]) as third:
            raise ZeroDivisionError
    with pytest.raises(RuntimeError):
        third.is_valid()
    with target.queries(pairing[1]) as fresh:
        assert fresh.count_truth_assignments() == 3


def test_invalid_engine_types(mgr, a, pairing):
    target = compile_target(mgr, pairing, a, [a])
    for invalid in ("cudd", object(), *(r for _, r in PAIRINGS if r != pairing[1])):
        with pytest.raises(TypeError):
            target.queries(invalid)


def test_native_delegation(mgr, a, pairing, monkeypatch):
    target = compile_target(mgr, pairing, a, [a])
    with target.queries(pairing[1]) as q:
        sat = Mock(return_value=True)
        count = Mock(return_value=7)
        clause = Mock(return_value=False)
        cube = Mock(return_value=True)
        valid = Mock(return_value=True)
        for operation, mock in (
            ("is_satisfiable", sat),
            ("count_truth_assignments", count),
            ("entails_clause", clause),
            ("is_implicant", cube),
            ("is_valid", valid),
        ):
            monkeypatch.setattr(q._inner, operation, mock)
        literals = [a, a, mgr.Not(a), mgr.TRUE(), mgr.FALSE()]
        assert q.is_satisfiable(literals)
        assert q.count_truth_assignments(literals) == 7
        assert not q.entails_clause(mgr.Or(a, mgr.Or(*literals[1:])))
        assert q.is_implicant(mgr.And(a, mgr.And(*literals[1:])))
        assert q.is_valid()
        for mock in (sat, count, clause, cube):
            mock.assert_called_once_with(literals)
        valid.assert_called_once_with()


def test_initialization_cleanup(mgr, a, monkeypatch):
    target = compile_target(mgr, PAIRINGS[2], a, [a])
    contexts = []
    original = QuerySession._index_atoms

    def record(context, atoms):
        contexts.append(context)
        return original(context, atoms)

    monkeypatch.setattr(QuerySession, "_index_atoms", record)

    def fail(*args, **kwargs):
        raise ValueError("native load failed")

    temporary_dirs = []
    original_temp = ddnnife_module.tempfile.TemporaryDirectory

    def temporary(*args, **kwargs):
        result = original_temp(*args, **kwargs)
        temporary_dirs.append(Path(result.name))
        return result

    monkeypatch.setattr(ddnnife_module.tempfile, "TemporaryDirectory", temporary)
    monkeypatch.setattr(ddnnife.Ddnnf, "from_file", fail)
    with pytest.raises(ValueError, match="native load failed"):
        target.queries(DdnnifeEngine)
    assert contexts[0]._normalizer._closed
    assert all(not path.exists() for path in temporary_dirs)


def test_ddnnife_rejects_partial_mapping(mgr, a, b):
    abstr = Abstractor({3: a, 7: b})
    native = D4CompiledTarget("o 1 0\nt 2 0\n1 2 1 0\n", 2, {3: 1})
    target = TheoryCompiledTarget(native, abstr, [a, b], env=mgr.env)
    with pytest.raises(AssertionError, match="D4 mapping"):
        DdnnifeEngine(target)


def test_ddnnife_absent_atom_is_mapped(mgr, a, b):
    target = compile_target(mgr, PAIRINGS[2], a, [a, b])
    assert target.abstr.get_id(b) in target.target.remapping
    with target.queries(DdnnifeEngine) as q:
        assert q.count_truth_assignments() == 2
        assert q.count_truth_assignments([b]) == 1
        assert not q.is_satisfiable([b, mgr.Not(b)])
        assert len(list(q.enumerate_truth_assignments())) == 2


def test_legacy_sdd_contradiction(mgr, a):
    target = compile_target(mgr, PAIRINGS[1], a, [a])
    assert not SddEngine(target).is_satisfiable([a, mgr.Not(a)])


def test_bound_environment(a, mgr, pairing):
    target = compile_target(mgr, pairing, a, [a])
    push_env(Environment())
    try:
        with target.queries(pairing[1]) as q:
            assert q._normalizer.env is mgr.env
            assert q.is_satisfiable([a])
            assert q.entails_clause(a)
            assert not q.entails_clause(mgr.Not(a))
    finally:
        pop_env()


def test_cleanup_continues_after_iterator_close_failure(mgr, a):
    target = compile_target(mgr, PAIRINGS[2], a, [a])
    q = target.queries(DdnnifeEngine)
    native = q._inner
    path = Path(native._tmpdir.name)
    closed = []

    def assignments():
        try:
            yield {a: True}
        finally:
            closed.append(True)
            if len(closed) == 1:
                raise ValueError("iterator close failed")

    q._inner.enumerate_truth_assignments = assignments
    broken, other = q.enumerate_truth_assignments(), q.enumerate_truth_assignments()
    next(broken)
    next(other)
    with pytest.raises(ValueError, match="iterator close failed"):
        q.close()
    assert not q._iterators
    assert len(closed) == 2
    assert q._normalizer._closed
    assert not path.exists()
    q.close()


def test_atom_index_initialization_failure(mgr, a, monkeypatch):
    target = compile_target(mgr, PAIRINGS[0], a, [a])
    contexts = []

    def fail(context, atoms):
        contexts.append(context)
        raise ValueError("index failed")

    monkeypatch.setattr(QuerySession, "_index_atoms", fail)
    with pytest.raises(ValueError, match="index failed"):
        target.queries(BddEngine)
    assert contexts[0]._normalizer._closed


def test_enumeration_failure_releases_iterator(mgr, a, pairing, monkeypatch):
    target = compile_target(mgr, pairing, a, [a])
    closed = []

    def fail():
        try:
            yield {a: True}
            raise ValueError("enumeration failed")
        finally:
            closed.append(True)

    with target.queries(pairing[1]) as q:
        monkeypatch.setattr(q._inner, "enumerate_truth_assignments", fail)
        iterator = q.enumerate_truth_assignments()
        assert next(iterator) == {a: True}
        with pytest.raises(ValueError, match="enumeration failed"):
            next(iterator)
        assert closed == [True]
        assert not q._iterators
        assert q.is_satisfiable()


def test_canonical_contradictions_and_constants(mgr, pairing):
    x = mgr.Symbol("canonical_query_x", INT)
    atom = mgr.GE(x, mgr.Int(2))
    equivalent = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    target = compile_target(mgr, pairing, atom, [atom])
    with target.queries(pairing[1]) as q:
        assert not q.is_satisfiable([atom, mgr.Not(equivalent)])
        assert q.count_truth_assignments([atom, mgr.Not(equivalent)]) == 0
        assert q.entails_clause(mgr.Or(atom, mgr.Not(equivalent)))
        assert q.is_implicant(mgr.And(atom, mgr.Not(equivalent)))
        assert q.is_satisfiable([mgr.Equals(x, x)])
        assert not q.is_satisfiable([mgr.Not(mgr.Equals(x, x))])


@pytest.mark.parametrize("truth", [True, False])
def test_rejects_stored_atoms_normalizing_to_constants(mgr, pairing, truth, monkeypatch):
    x = mgr.Symbol("stored_constant_x", INT)
    atom = mgr.Equals(x, x if truth else mgr.Plus(x, mgr.Int(1)))
    abstr = Abstractor({1: atom})
    native = pairing[0]().compile(atom, abstr, all_vars=[atom])
    target = TheoryCompiledTarget(native, abstr, [atom], env=mgr.env)
    contexts = []
    original = QuerySession._index_atoms

    def record(context, atoms):
        contexts.append(context)
        return original(context, atoms)

    monkeypatch.setattr(QuerySession, "_index_atoms", record)
    with pytest.raises(AssertionError, match="Projection atoms must not normalize to constants"):
        target.queries(pairing[1])
    assert len(contexts) == 1
    assert contexts[0]._atom_index == {}
    assert contexts[0]._normalizer._closed


def test_unstarted_enumeration_is_closed(mgr, a, pairing):
    target = compile_target(mgr, pairing, a, [a])
    q = target.queries(pairing[1])
    iterator = q.enumerate_truth_assignments()
    q.close()
    assert not q._iterators
    with pytest.raises(StopIteration):
        next(iterator)


def test_enumeration_setup_failure_unregisters(mgr, a, monkeypatch):
    target = compile_target(mgr, PAIRINGS[0], a, [a])
    with target.queries(BddEngine) as q:
        monkeypatch.setattr(q._inner, "enumerate_truth_assignments", Mock(side_effect=ValueError("setup failed")))
        iterator = q.enumerate_truth_assignments()
        with pytest.raises(ValueError, match="setup failed"):
            next(iterator)
        assert not q._iterators


def test_closed_unstarted_generators_are_not_retained(mgr, a, pairing):
    target = compile_target(mgr, pairing, a, [a])
    with target.queries(pairing[1]) as q:
        for _ in range(1000):
            iterator = q.enumerate_truth_assignments()
            iterator.close()
        assert not q._iterators
        assert q.is_satisfiable()


def test_independent_enumerations_and_explicit_close(mgr, a, b, pairing):
    target = compile_target(mgr, pairing, mgr.Or(a, b), [b, a])
    with target.queries(pairing[1]) as q:
        first = q.enumerate_truth_assignments()
        second = q.enumerate_truth_assignments()
        assert next(first) == next(second)
        assert q._iterators == {first.gi_yieldfrom, second.gi_yieldfrom}
        first.close()
        assert q._iterators == {second.gi_yieldfrom}
        assert len(list(second)) == 2
        assert not q._iterators
        assert q.count_truth_assignments() == 3
        first = q.enumerate_truth_assignments()
        second = q.enumerate_truth_assignments()
        next(first)
        next(second)
        q.close()
        assert list(first) == list(second) == []


def test_engine_close_failure_still_closes_normalizer(mgr, a, monkeypatch):
    target = compile_target(mgr, PAIRINGS[0], a, [a])
    q = target.queries(BddEngine)
    iterator = q.enumerate_truth_assignments()
    next(iterator)
    engine_iterator = iterator.gi_yieldfrom

    def fail():
        assert engine_iterator.gi_frame is None
        raise ValueError("engine close failed")

    monkeypatch.setattr(q._inner, "close", fail)
    with pytest.raises(ValueError, match="engine close failed"):
        q.close()
    assert q._normalizer._closed
    assert not q._iterators
    assert list(iterator) == []
    q.close()
