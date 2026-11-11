"""Construction semantics, projection, normalization, abstraction reuse, and deterministic registration."""

import json
import os
import subprocess
import sys

import pytest
from pysmt.fnode import FNode
from pysmt.typing import INT

from tddnnf import TheoryCompilation
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.normalization.normalizer import NormalizerWalker
from tddnnf.queries import SddEngine
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
        equivalent(mgr, target.to_pysmt(), expected)
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
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("theory", [False, True])
def test_node_id_atom_order(mgr, backend, strategy, explicit, theory):
    z, a, y, b = [mgr.Symbol(name, INT) if theory else mgr.Symbol(name) for name in ("z", "a", "y", "b")]
    if theory:
        raw = [mgr.GE(mgr.Times(mgr.Int(2), symbol), mgr.Int(4)) for symbol in (z, a, y, b)]
        # Create canonical atoms in an order different from both spelling and raw node IDs.
        with NormalizerWalker(mgr.env) as normalizer:
            y, z, b, a = [normalizer.normalize(atom) for atom in (raw[2], raw[0], raw[3], raw[1])]
        assert all(atom not in (z, a, y, b) for atom in raw)
    else:
        raw = [z, a, y, b]
    projection = [raw[1], mgr.Not(raw[0]), raw[1]] if explicit else None
    with TheoryCompilation(mgr.And(*raw[:2]), projection, env=mgr.env) as compilation:
        assert compilation.project_on == ((a, z) if explicit else (z, a))
        target = getattr(compilation, strategy)(backend(), [mgr.And(*raw[2:])])
        assert target.projection_atoms == compilation.project_on
        assert dict(target.abstr.id_to_atom) == dict(enumerate((*compilation.project_on, y, b), 1))


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
def test_reduced_compilation_normalizes_lemmas(mgr, backend, x, p):
    raw_atom = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    canonical_atom = mgr.GE(x, mgr.Int(2))
    with TheoryCompilation(p, [p, canonical_atom], env=mgr.env) as compilation:
        target = compilation.compile_treduced(backend(), [raw_atom])
    equivalent(mgr, target.to_pysmt(), mgr.And(p, canonical_atom))
    assert set(target.abstr.id_to_atom.values()) == {p, canonical_atom}
    assert target.projection_atoms == (p, canonical_atom)


@pytest.mark.parametrize("backend", BACKENDS)
def test_extended_compilation_normalizes_lemmas(mgr, backend, x, p):
    raw_atom = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    canonical_atom = mgr.GE(x, mgr.Int(2))
    with TheoryCompilation(p, [p, canonical_atom], env=mgr.env) as compilation:
        target = compilation.compile_textended(backend(), [raw_atom])
    equivalent(mgr, target.to_pysmt(), mgr.Or(p, mgr.Not(canonical_atom)))
    assert set(target.abstr.id_to_atom.values()) == {p, canonical_atom}
    assert target.projection_atoms == (p, canonical_atom)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_normalizes_and_deduplicates_projection(mgr, backend, strategy, x, p):
    absent = mgr.Symbol("absent")
    canonical_atom = mgr.GE(x, mgr.Int(2))
    duplicate = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    with TheoryCompilation(p, [absent, canonical_atom, mgr.Not(duplicate), p], env=mgr.env) as compilation:
        assert compilation.project_on == (absent, canonical_atom, p)
        target = getattr(compilation, strategy)(backend(), [])
    assert target.projection_atoms == (absent, canonical_atom, p)
    assert dict(target.abstr.id_to_atom) == {1: absent, 2: canonical_atom, 3: p}
    equivalent(mgr, target.to_pysmt(), p)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_compiler_reuse_preserves_independent_results(mgr, backend, strategy):
    p, q, absent, r = [mgr.Symbol(name) for name in ("p", "q", "absent", "r")]
    compiler = backend()
    with TheoryCompilation(p, [absent, q, p], env=mgr.env) as compilation:
        first = getattr(compilation, strategy)(compiler, [q])
        second = getattr(compilation, strategy)(compiler, [])
    with TheoryCompilation(r, env=mgr.env) as compilation:
        third = getattr(compilation, strategy)(compiler, [])
    expected = mgr.And(p, q) if strategy == "compile_treduced" else mgr.Or(p, mgr.Not(q))
    equivalent(mgr, first.to_pysmt(), expected)
    equivalent(mgr, second.to_pysmt(), p)
    equivalent(mgr, third.to_pysmt(), r)
    assert first.projection_atoms == second.projection_atoms == (absent, q, p)
    assert dict(first.abstr.id_to_atom) == dict(second.abstr.id_to_atom) == {1: absent, 2: q, 3: p}
    assert second.abstr is not first.abstr
    assert third.projection_atoms == (r,)
    assert dict(third.abstr.id_to_atom) == {1: r}
    if backend is SddCompiler:
        assert SddEngine(second).count_truth_assignments() == 4


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


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("backend", BACKENDS)
def test_supplied_abstraction_preserves_ids(mgr, strategy, backend):
    added, last, atom = [mgr.Symbol(name) for name in ("z", "b", "a")]
    abstractor = Abstractor({2: atom})
    formula = mgr.And(atom, last, added)
    with TheoryCompilation(formula, env=mgr.env) as compilation:
        target = getattr(compilation, strategy)(backend(), [], abstractor=abstractor)
    assert target.abstr is abstractor
    assert dict(abstractor.id_to_atom) == {2: atom, 3: added, 4: last}
    assert target.abstr.get_id(atom) == 2
    assert target.abstr.get_id(added) == 3
    assert target.abstr.get_id(last) == 4
    assert target.abstr.get_atom(2) is atom
    equivalent(mgr, target.to_pysmt(), formula)


@pytest.mark.parametrize("entry", ["true", "false", "and", "or"])
@pytest.mark.parametrize("negated", [False, True])
def test_rejects_compound_and_constant_projection(mgr, entry, negated):
    a, b = mgr.Symbol("a"), mgr.Symbol("b")
    value = {"true": mgr.TRUE(), "false": mgr.FALSE(), "and": mgr.And(a, b), "or": mgr.Or(a, b)}[entry]
    value = mgr.Not(value) if negated else value
    with pytest.raises(ValueError, match="Projection entries"):
        TheoryCompilation(a, [value], env=mgr.env)


def test_ids_across_hash_seeds_and_backends():
    code = """
import json
from pysmt.shortcuts import Symbol, And, Or
from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
atoms = {name: Symbol(name) for name in ["z", "a", "m", "absent", "lemma"]}
results = []
for backend in [BddCompiler, SddCompiler, D4Compiler]:
    for strategy in ["compile_treduced", "compile_textended"]:
        for projection in [None, [atoms["absent"], atoms["m"]]]:
            with TheoryCompilation(And(atoms["z"], Or(atoms["a"], atoms["m"])), projection) as c:
                t = getattr(c, strategy)(backend(), [atoms["lemma"]])
                results.append([ [str(a) for a in t.projection_atoms], t.abstr.to_dict() ])
print(json.dumps(results, sort_keys=True))
"""
    outputs = [
        subprocess.check_output(
            [sys.executable, "-c", code], env={**os.environ, "PYTHONHASHSEED": str(seed)}, text=True
        )
        for seed in [0, 1, 99]
    ]
    assert outputs[0] == outputs[1] == outputs[2]
    rows = json.loads(outputs[0])
    assert rows[:4] == rows[4:8] == rows[8:]


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
