"""Public sessions release engines, normalizers, and iterators on close and failures."""

from pathlib import Path
from unittest.mock import Mock

import ddnnife
import pytest

import tddnnf.queries.ddnnife_engine as ddnnife_module
from tddnnf.queries import BddEngine, DdnnifeEngine
from tddnnf.queries.session import QuerySession
from tests.support import PAIRINGS, compile_target


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
