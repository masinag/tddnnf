"""Normalized lemmas, constant semantics, and independent compilation statistics."""

import pytest

from tddnnf import TheoryCompilation
from tddnnf.compilers.d4 import D4Compiler
from tests.support import BACKENDS, STRATEGIES, equivalent


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("strategy,expected_shape", [("compile_treduced", "and"), ("compile_textended", "or-negation")])
def test_compilation_normalizes_lemmas(mgr, backend, x, p, strategy, expected_shape):
    raw_atom = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    canonical_atom = mgr.GE(x, mgr.Int(2))
    with TheoryCompilation(p, [p, canonical_atom], env=mgr.env) as compilation:
        target = getattr(compilation, strategy)(backend(), [raw_atom])
    expected = mgr.And(p, canonical_atom) if expected_shape == "and" else mgr.Or(p, mgr.Not(canonical_atom))
    equivalent(mgr, target.to_pysmt(), expected)
    assert set(target.abstr.id_to_atom.values()) == {p, canonical_atom}
    assert target.projection_atoms == (p, canonical_atom)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_compilation_statistics(mgr, backend, strategy):
    p, q, absent = [mgr.Symbol(name) for name in ("p", "q", "absent")]
    compiler = backend()
    first_log, second_log = {}, {}
    with TheoryCompilation(p, [absent, q, p], env=mgr.env) as compilation:
        getattr(compilation, strategy)(compiler, [q], first_log)
        snapshot = dict(first_log)
        getattr(compilation, strategy)(compiler, [], second_log)
    assert first_log == snapshot
    assert first_log["n_lemmas"] == 1
    assert second_log["n_lemmas"] == 0
    assert first_log["n_projection_atoms"] == second_log["n_projection_atoms"] == 3
    assert {"build_time", "compile_time", "n_atoms", "n_proj_vars"} <= first_log.keys()
    if backend is D4Compiler:
        assert {"register_atoms_time", "write_circuit_time", "run_d4_time"} <= first_log.keys()


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("value", [True, False])
def test_compound_constants_and_lemmas(mgr, backend, strategy, value):
    phi = mgr.Or(mgr.Bool(value), mgr.FALSE())
    lemmas = [mgr.TRUE(), mgr.Bool(value)]
    expected = value if strategy == "compile_treduced" else True
    with TheoryCompilation(phi, env=mgr.env) as compilation:
        target = getattr(compilation, strategy)(backend(), lemmas)
    equivalent(mgr, target.to_pysmt(), mgr.Bool(expected))
    assert target.projection_atoms == ()
