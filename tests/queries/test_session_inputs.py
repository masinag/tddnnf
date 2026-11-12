"""Session formula flattening, assumption validation, and constant inputs."""

from itertools import product

import ddnnife
import pytest
from pysmt.typing import INT

from tddnnf.queries import DdnnifeEngine
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
@pytest.mark.parametrize("prefix", ["empty", "true", "false", "complementary"])
def test_unknown_atom_rejected_before_shortcuts(mgr, a, b, c, pairing, operation, prefix):
    target = compile_target(mgr, pairing, mgr.Or(a, b), [a, b])
    original_ids = dict(target.abstr.atom_to_id)
    with target.queries(pairing[1]) as query:
        literals = [
            *{"empty": [], "true": [mgr.TRUE()], "false": [mgr.FALSE()], "complementary": [a, mgr.Not(a)]}[prefix],
            c,
        ]
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


@pytest.mark.parametrize("operation", ["is_satisfiable", "count_truth_assignments"])
@pytest.mark.parametrize("case", ["compound", "non-formula"])
def test_malformed_assumptions(mgr, a, b, pairing, operation, case):
    target = compile_target(mgr, pairing, mgr.Or(a, b), [a, b])
    literals = [mgr.And(a, b)] if case == "compound" else [42]
    with target.queries(pairing[1]) as query:
        with pytest.raises(ValueError):
            getattr(query, operation)(literals)


@pytest.mark.parametrize("operation", ["entails_clause", "is_implicant"])
def test_wrong_formula_connective(mgr, a, b, pairing, operation):
    target = compile_target(mgr, pairing, mgr.Or(a, b), [a, b])
    formula = mgr.Or(a, mgr.And(a, b)) if operation == "entails_clause" else mgr.And(a, mgr.Or(a, b))
    with target.queries(pairing[1]) as query:
        with pytest.raises(ValueError):
            getattr(query, operation)(formula)
