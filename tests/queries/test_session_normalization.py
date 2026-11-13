"""Canonical literal alignment, ambiguity rejection, environment binding, and native delegation."""

from unittest.mock import Mock

import pytest
from pysmt.environment import Environment, pop_env, push_env
from pysmt.typing import INT

from tddnnf import TheoryCompiledTarget
from tddnnf.core.abstraction import Abstractor
from tddnnf.queries.session import QuerySession
from tests.support import compile_target


def test_equivalent_syntax_and_polarity(mgr, pairing):
    x, y = mgr.Symbol("session_x", INT), mgr.Symbol("session_y", INT)
    atom, opposite = mgr.LE(y, x), mgr.LT(x, y)
    scaled = mgr.LE(mgr.Times(mgr.Int(2), y), mgr.Times(mgr.Int(2), x))
    abstr = Abstractor({1: atom})
    native = pairing[0]().compile(atom, abstr, all_atoms=[atom])
    target = TheoryCompiledTarget(native, abstr, [atom], env=mgr.env)
    with target.queries(pairing[1]) as q:
        assert q.is_satisfiable([scaled])
        assert not q.is_satisfiable([opposite])
        assert q.count_truth_assignments([atom, opposite]) == 0
        assert q.entails_clause(scaled)
        assert q.is_implicant(mgr.Not(opposite))
        assert list(q.enumerate_truth_assignments()) == [{atom: True}]


@pytest.mark.parametrize("operation", ["entails_clause", "is_implicant"])
def test_canonical_literal_delegation(mgr, pairing, monkeypatch, operation):
    x, y = mgr.Symbol("session_x", INT), mgr.Symbol("session_y", INT)
    atom, opposite = mgr.LE(y, x), mgr.LT(x, y)
    scaled = mgr.LE(mgr.Times(mgr.Int(2), y), mgr.Times(mgr.Int(2), x))
    abstr = Abstractor({1: atom})
    native = pairing[0]().compile(atom, abstr, all_atoms=[atom])
    target = TheoryCompiledTarget(native, abstr, [atom], env=mgr.env)
    formula = mgr.Or(scaled, opposite) if operation == "entails_clause" else mgr.And(scaled, mgr.Not(opposite))
    expected = [atom, mgr.Not(atom)] if operation == "entails_clause" else [atom, atom]
    with target.queries(pairing[1]) as q:
        delegate = Mock(return_value=True)
        monkeypatch.setattr(q._inner, operation, delegate)
        assert getattr(q, operation)(formula)
        delegate.assert_called_once_with(expected)


def test_ambiguous_projection_is_rejected(mgr, pairing):
    x, y = mgr.Symbol("session_x", INT), mgr.Symbol("session_y", INT)
    atom, opposite = mgr.LE(y, x), mgr.LT(x, y)
    abstr = Abstractor({1: atom})
    native = pairing[0]().compile(atom, abstr, all_atoms=[atom])
    ambiguous = TheoryCompiledTarget(native, abstr, [atom, opposite], env=mgr.env)
    with pytest.raises(ValueError, match="Ambiguous"):
        ambiguous.queries(pairing[1])


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
    native = pairing[0]().compile(atom, abstr, all_atoms=[atom])
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
