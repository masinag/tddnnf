"""Deterministic atom registration, supplied abstractions, and compiler reuse."""

import json
import os
import subprocess
import sys

import pytest
from pysmt.typing import INT

from tddnnf import TheoryCompilation
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.normalization.normalizer import NormalizerWalker
from tests.support import BACKENDS, STRATEGIES, equivalent


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
        assert compilation.atoms == ((a, z) if explicit else (z, a))
        if backend is D4Compiler and strategy == "compile_textended":
            with pytest.raises(NotImplementedError, match="universal"):
                compilation.compile_textended(backend(), [mgr.And(*raw[2:])])
            return
        target = getattr(compilation, strategy)(backend(), [mgr.And(*raw[2:])])
        assert target.projection_atoms == compilation.atoms
        assert dict(target.abstr.id_to_atom) == dict(enumerate((*compilation.atoms, y, b), 1))


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_compiler_reuse_preserves_independent_results(mgr, backend, strategy):
    p, q, absent, r = [mgr.Symbol(name) for name in ("p", "q", "absent", "r")]
    compiler = backend()
    first_log, second_log = {}, {}
    with TheoryCompilation(p, [absent, q, p], env=mgr.env) as compilation:
        first = getattr(compilation, strategy)(compiler, [q], first_log)
        snapshot = dict(first_log)
        second = getattr(compilation, strategy)(compiler, [], second_log)
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


def test_ids_across_hash_seeds_and_backends():
    code = """
import json
from pysmt.shortcuts import Symbol, And, Or
from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.compilers.d4 import D4Compiler
atoms = {name: Symbol(name) for name in ["z", "a", "m", "absent", "lemma"]}
results = []
for backend in [BddCompiler, SddCompiler, D4Compiler]:
    for strategy in ["compile_treduced", "compile_textended"]:
        for projection in [None, [atoms["absent"], atoms["m"], atoms["z"], atoms["a"]]]:
            with TheoryCompilation(And(atoms["z"], Or(atoms["a"], atoms["m"])), projection) as c:
                try:
                    t = getattr(c, strategy)(backend(), [atoms["lemma"]])
                except NotImplementedError:
                    assert backend is D4Compiler and strategy == "compile_textended"
                    results.append(None)
                else:
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
    assert rows[:4] == rows[4:8]
    assert rows[8:10] == rows[:2]
    assert rows[10:] == [None, None]
