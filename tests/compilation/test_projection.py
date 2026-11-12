"""Public normalization, projection selection, and invalid projection entries."""

import pytest
from pysmt.fnode import FNode
from pysmt.typing import INT

from tddnnf import TheoryCompilation
from tests.support import BACKENDS, STRATEGIES, equivalent, shannon_forget


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("projection", [None, [], ["b"], ["absent", "b", "absent"]])
@pytest.mark.parametrize("constant", [None, True, False])
def test_projected_semantics(mgr, backend, strategy, projection, constant):
    a, b, c, absent = [mgr.Symbol(name) for name in ("a", "b", "c", "absent")]
    phi = mgr.And(a, b) if constant is None else mgr.Bool(constant)
    lemmas = [mgr.Or(b, c)] if constant is None else []
    selected = None if projection is None else [mgr.Symbol(name) for name in projection]
    with TheoryCompilation(phi, project_on=selected, env=mgr.env) as compilation:
        target = getattr(compilation, strategy)(backend(), lemmas)
        combined = (
            mgr.And(phi, *lemmas)
            if strategy == "compile_treduced"
            else mgr.Or(phi, *(mgr.Not(lemma) for lemma in lemmas))
        )
        forgotten = [atom for atom in combined.get_atoms() if atom not in compilation.project_on]
        expected = shannon_forget(mgr, combined, forgotten)
        vocabulary = (
            list(dict.fromkeys(selected)) if selected is not None else sorted(phi.get_atoms(), key=FNode.node_id)
        )
        assert target.projection_atoms == tuple(vocabulary)
        assert target.to_pysmt().get_atoms() <= set(target.projection_atoms)
        ordered = list(target.projection_atoms) + sorted(
            combined.get_atoms() - set(target.projection_atoms), key=FNode.node_id
        )
        assert [target.abstr.get_atom(i + 1) for i in range(len(ordered))] == ordered
    # Closing compilation must not invalidate the result.
    equivalent(mgr, target.to_pysmt(), expected)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("negated", [False, True])
def test_constant_normalizing_projection_atoms(mgr, backend, strategy, negated):
    p = mgr.Symbol("p")
    x = mgr.Symbol("x", INT)
    atoms = [mgr.GE(x, x), mgr.LT(x, x)]
    entries = [mgr.Not(atom) for atom in atoms] if negated else atoms
    with TheoryCompilation(p, [*entries, p], env=mgr.env) as compilation:
        assert [compilation.normalize(atom) for atom in atoms] == [mgr.TRUE(), mgr.FALSE()]
        assert compilation.project_on == (p,)
        target = getattr(compilation, strategy)(backend(), [])
        assert target.projection_atoms == (p,)
        assert target.abstr.var_count == 1
        assert target.abstr.get_atom(1) == p
        assert all(atom not in target.abstr for atom in [*entries, mgr.TRUE(), mgr.FALSE()])
        equivalent(mgr, target.to_pysmt(), p)


def test_normalizes_input_and_default_projection(mgr, x, p):
    raw_atom = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    canonical_atom = mgr.GE(x, mgr.Int(2))
    with TheoryCompilation(mgr.And(p, raw_atom), env=mgr.env) as compilation:
        assert compilation.phi == mgr.And(p, canonical_atom)
        assert set(compilation.project_on) == {p, canonical_atom}


def test_normalizes_projection_to_positive_atom(mgr, x, p):
    with TheoryCompilation(p, [mgr.LT(x, mgr.Int(2))], env=mgr.env) as compilation:
        assert compilation.project_on == (mgr.GE(x, mgr.Int(2)),)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_normalizes_and_deduplicates_projection(mgr, backend, strategy, x, p):
    absent = mgr.Symbol("absent")
    canonical_atom = mgr.GE(x, mgr.Int(2))
    duplicate = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    with TheoryCompilation(p, [absent, canonical_atom, mgr.Not(duplicate), p], env=mgr.env) as compilation:
        assert compilation.project_on == (absent, canonical_atom, p)
        target = getattr(compilation, strategy)(backend(), [duplicate])
    assert target.projection_atoms == (absent, canonical_atom, p)
    assert dict(target.abstr.id_to_atom) == {1: absent, 2: canonical_atom, 3: p}
    expected = mgr.And(p, canonical_atom) if strategy == "compile_treduced" else mgr.Or(p, mgr.Not(canonical_atom))
    equivalent(mgr, target.to_pysmt(), expected)


@pytest.mark.parametrize("entry", ["true", "false", "and", "or"])
@pytest.mark.parametrize("negated", [False, True])
def test_rejects_compound_and_constant_projection(mgr, entry, negated):
    a, b = mgr.Symbol("a"), mgr.Symbol("b")
    value = {"true": mgr.TRUE(), "false": mgr.FALSE(), "and": mgr.And(a, b), "or": mgr.Or(a, b)}[entry]
    value = mgr.Not(value) if negated else value
    with pytest.raises(ValueError, match="Projection entries"):
        TheoryCompilation(a, [value], env=mgr.env)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("value", [True, False])
def test_constant_lemmas_with_empty_projection(mgr, backend, strategy, value):
    phi = mgr.Or(mgr.Bool(value), mgr.FALSE())
    lemmas = [mgr.TRUE(), mgr.Bool(value)]
    expected = value if strategy == "compile_treduced" else True
    with TheoryCompilation(phi, env=mgr.env) as compilation:
        target = getattr(compilation, strategy)(backend(), lemmas)
    equivalent(mgr, target.to_pysmt(), mgr.Bool(expected))
    assert target.projection_atoms == ()
