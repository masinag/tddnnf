"""Public sessions normalize literals and formulas, validate vocabulary, bind environments, and delegate queries."""

from itertools import product
from unittest.mock import Mock

import ddnnife
import pytest
from pysmt.environment import Environment, pop_env, push_env
from pysmt.typing import BOOL, INT

from tddnnf import TheoryCompiledTarget
from tddnnf.core.abstraction import Abstractor
from tddnnf.queries import DdnnifeEngine
from tddnnf.queries.session import QuerySession
from tests.support import PAIRINGS, compile_target


def test_literals_constants_and_validation(mgr, a, b, pairing):
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
        for assumptions in ([mgr.And(a, b)], [42]):
            for operation in (q.is_satisfiable, q.count_truth_assignments):
                with pytest.raises(ValueError):
                    operation(assumptions)
        for operation, formula in (
            (q.entails_clause, mgr.Or(a, mgr.And(a, b))),
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
    native = pairing[0]().compile(mgr.And(a, forgotten), abstr, project_on=[c, b, a])
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


def test_equivalent_syntax_polarity_and_ambiguity(mgr, pairing, monkeypatch):
    x, y = mgr.Symbol("session_x", INT), mgr.Symbol("session_y", INT)
    atom = mgr.LE(y, x)
    opposite = mgr.LT(x, y)
    scaled = mgr.LE(mgr.Times(mgr.Int(2), y), mgr.Times(mgr.Int(2), x))
    abstr = Abstractor({1: atom})
    native = pairing[0]().compile(atom, abstr, project_on=[atom])
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
    native = pairing[0]().compile(atom, abstr, project_on=[atom])
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


@pytest.mark.parametrize("pairing", PAIRINGS)
@pytest.mark.parametrize("truth", [True, False])
def test_query_constants_and_negation(mgr, pairing, truth):
    x = mgr.Symbol("constant_x", INT)
    atom = mgr.Equals(x, x if truth else mgr.Plus(x, mgr.Int(1)))
    target = compile_target(mgr, pairing, mgr.TRUE(), [])
    if pairing[1] is DdnnifeEngine:
        with pytest.raises(ddnnife.InternalError):
            target.queries(pairing[1])
        return
    with target.queries(pairing[1]) as q:
        for literal in (mgr.Bool(truth), atom):
            assert q.is_satisfiable([literal]) == truth
            assert q.is_satisfiable([mgr.Not(literal)]) != truth
            assert q.entails_clause(literal) == truth
            assert q.is_implicant(literal)


@pytest.mark.parametrize("operation", ["is_satisfiable", "count_truth_assignments", "entails_clause", "is_implicant"])
def test_unknown_atom_rejected_before_shortcuts(mgr, a, b, c, pairing, operation):
    target = compile_target(mgr, pairing, mgr.Or(a, b), [a, b])
    original_ids = dict(target.abstr.atom_to_id)
    with target.queries(pairing[1]) as query:
        for prefix in ([], [mgr.TRUE()], [mgr.FALSE()], [a, mgr.Not(a)]):
            literals = [*prefix, c]
            # Nested formulas must validate their entire vocabulary before applying shortcuts.
            if operation == "entails_clause":
                argument = mgr.Or(a, mgr.Or(literals))
            elif operation == "is_implicant":
                argument = mgr.And(a, mgr.And(literals))
            else:
                argument = literals
            with pytest.raises(ValueError, match="not .*projection"):
                getattr(query, operation)(argument)
        assert dict(target.abstr.atom_to_id) == original_ids
