"""Normalization regressions through the public query session."""

import pytest
from pysmt.typing import INT

from tests.test_query_sessions import PAIRINGS, compile_target


@pytest.mark.parametrize("pairing", PAIRINGS)
@pytest.mark.parametrize("truth", [True, False])
def test_query_constants_and_negation(mgr, pairing, truth):
    x = mgr.Symbol("constant_x", INT)
    atom = mgr.Equals(x, x if truth else mgr.Plus(x, mgr.Int(1)))
    target = compile_target(mgr, pairing, mgr.TRUE(), [])
    with target.queries(pairing[1]) as q:
        for literal in (mgr.Bool(truth), atom):
            assert q.is_satisfiable([literal]) == truth
            assert q.is_satisfiable([mgr.Not(literal)]) != truth
            assert q.entails_clause(literal) == truth
            assert q.is_implicant(literal)
