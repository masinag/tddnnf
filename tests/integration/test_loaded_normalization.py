"""Normalized queries retain meaning after loading into a fresh environment."""

import pytest
from pysmt.environment import Environment
from pysmt.typing import INT

from tddnnf import TheoryCompilation
from tddnnf.core.containers import TheoryCompiledTarget
from tests.support import PAIRINGS


@pytest.mark.parametrize("pairing", PAIRINGS)
def test_fresh_query_context_handles_direct_and_loaded_targets(mgr, tmp_path, pairing):
    x, p = mgr.Symbol("x", INT), mgr.Symbol("p")
    with TheoryCompilation(mgr.And(p, mgr.GE(x, mgr.Int(2))), env=mgr.env) as compilation:
        target = compilation.compile_treduced(pairing[0](), [])
    target.save(tmp_path / "artifact")
    loaded = TheoryCompiledTarget.load(tmp_path / "artifact", type(target.target), env=Environment())
    for container in (target, loaded):
        fm = container.env.formula_manager
        equivalent_atom = fm.GE(fm.Times(fm.Int(2), fm.Symbol("x", INT)), fm.Int(4))
        with container.queries(pairing[1]) as query:
            assert query.is_satisfiable([equivalent_atom])
            assert not query.is_satisfiable([fm.Not(equivalent_atom)])
