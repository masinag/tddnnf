"""Compilation contracts shared by the three native adapters."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from pysmt.smtlib.printers import to_smtlib
from pysmt.typing import INT

from tddnnf import CompilationContext, TheoryCompilation
from tddnnf.builders.extended import TExtendedBuilder
from tddnnf.builders.reduced import TReducedBuilder
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.normalization.normalizer import NormalizerWalker
from tests.conftest import shannon_forget

BACKENDS = [BddCompiler, SddCompiler, D4Compiler]
STRATEGIES = ["compile_treduced", "compile_textended"]


def equivalent(mgr, actual, expected):
    with mgr.env.factory.Solver() as solver:
        solver.add_assertion(mgr.Not(mgr.Iff(actual, expected)))
        assert not solver.solve()


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
        equivalent(mgr, target.to_pysmt(mgr), expected)
        vocabulary = (
            list(dict.fromkeys(selected))
            if selected is not None
            else sorted(phi.get_atoms(), key=lambda atom: to_smtlib(atom, daggify=False))
        )
        assert target.projection_atoms == vocabulary
        assert target.to_pysmt(mgr).get_atoms() <= set(target.projection_atoms)
        ordered = target.projection_atoms + sorted(
            combined.get_atoms() - set(target.projection_atoms), key=lambda atom: to_smtlib(atom, daggify=False)
        )
        assert [target.abstr.get_atom(i + 1) for i in range(len(ordered))] == ordered
    # Closing compilation must not invalidate the result.
    equivalent(mgr, target.to_pysmt(mgr), expected)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_normalized_projection_and_compiler_reuse(mgr, backend, strategy):
    p, absent = mgr.Symbol("p"), mgr.Symbol("absent")
    x = mgr.Symbol("x", INT)
    atom = mgr.GE(x, mgr.Int(2))
    duplicate = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    compiler = backend()
    first_log, second_log = {}, {}
    with TheoryCompilation(p, [absent, atom, mgr.Not(duplicate), p], env=mgr.env) as compilation:
        first = getattr(compilation, strategy)(compiler, [duplicate], first_log)
        assert first.projection_atoms == [absent, compilation.normalize(atom), p]
        assert [first.abstr.get_id(a) for a in first.projection_atoms] == [1, 2, 3]
        snapshot = dict(first_log)
        second = getattr(compilation, strategy)(compiler, [], second_log)
        assert second.abstr is not first.abstr
        assert first_log == snapshot
    with TheoryCompilation(p, env=mgr.env) as compilation:
        third = getattr(compilation, strategy)(compiler, [])
        assert third.abstr.var_count == 1
        assert third.abstr.get_id(p) == 1
    assert {
        "build_time",
        "compile_time",
        "n_lemmas",
        "n_projection_atoms",
        "n_atoms",
        "n_proj_vars",
    } <= first_log.keys()
    if backend is D4Compiler:
        assert {"register_atoms_time", "write_circuit_time", "run_d4_time"} <= first_log.keys()
    # Native compilers store only configuration, never per-call abstractions/loggers.
    assert all(not isinstance(value, (Abstractor, dict)) for value in vars(compiler).values())


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("options", [{}, {"auto_gc_and_minimize": True}, {"auto_gc_and_minimize": False}])
def test_sdd_native_options(mgr, strategy, options):
    from pysdd.sdd import SddManager, Vtree

    compiler = SddCompiler(vtree_type="right", **options)
    # Compare actual native configuration and vtree with native construction.
    a, b, c = [mgr.Symbol(name) for name in ("a", "b", "c")]
    phi = mgr.And(mgr.Or(a, b), c)
    with TheoryCompilation(phi, env=mgr.env) as compilation:
        target = getattr(compilation, strategy)(compiler, [])
        manager = target.target.manager
        assert bool(manager.is_auto_gc_and_minimize_on()) is options.get("auto_gc_and_minimize", True)
        expected = SddManager.from_vtree(Vtree(var_count=3, vtree_type="right"))
        assert manager.vtree().left().is_leaf() == expected.vtree().left().is_leaf()
        equivalent(mgr, target.to_pysmt(mgr), phi)


@pytest.mark.parametrize("builder", [TReducedBuilder, TExtendedBuilder])
@pytest.mark.parametrize("backend", BACKENDS)
def test_builder_preserves_abstraction(mgr, builder, backend):
    atom, added = mgr.Symbol("a"), mgr.Symbol("b")
    abstractor = Abstractor({2: atom})
    formula = mgr.And(atom, added)
    target = builder(backend(), env=mgr.env).build(formula, [], abstractor)
    assert target.abstr is abstractor
    assert target.abstr.get_id(atom) == 2
    assert target.abstr.get_id(added) == 3
    assert target.abstr.get_atom(2) is atom
    equivalent(mgr, target.to_pysmt(mgr), formula)


@pytest.mark.parametrize("bad", ["sdd", SddCompiler, object(), None])
def test_invalid_compiler(mgr, bad):
    with TheoryCompilation(mgr.TRUE(), env=mgr.env) as compilation:
        for strategy in STRATEGIES:
            with pytest.raises(TypeError, match="instance"):
                getattr(compilation, strategy)(bad, [])


@pytest.mark.parametrize("entry", ["true", "false", "and", "or"])
def test_rejects_compound_and_constant_projection(mgr, entry):
    a, b = mgr.Symbol("a"), mgr.Symbol("b")
    value = {"true": mgr.TRUE(), "false": mgr.FALSE(), "and": mgr.And(a, b), "or": mgr.Or(a, b)}[entry]
    with pytest.raises(ValueError, match="Projection entries"):
        TheoryCompilation(a, [value], env=mgr.env)


@pytest.mark.parametrize("session_type", [TheoryCompilation, NormalizerWalker])
def test_session_lifecycle(mgr, session_type):
    assert CompilationContext is TheoryCompilation
    session = session_type(mgr.TRUE(), env=mgr.env) if session_type is TheoryCompilation else session_type(mgr.env)
    with pytest.raises(LookupError), session:
        raise LookupError("body failure")
    session.close()
    with pytest.raises(RuntimeError, match="closed"):
        session.normalize(mgr.TRUE())
    with pytest.raises(RuntimeError, match="closed"):
        session.__enter__()
    if session_type is TheoryCompilation:
        with pytest.raises(RuntimeError, match="closed"):
            session.compile_treduced(BddCompiler(), [])


def test_partial_initialization_cleanup(mgr, monkeypatch):
    solver = Mock()
    solver.converter = Mock()
    monkeypatch.setattr(mgr.env.factory, "Solver", Mock(return_value=solver))
    with pytest.raises(ValueError, match="Projection entries"):
        TheoryCompilation(mgr.TRUE(), project_on=[mgr.TRUE()], env=mgr.env)
    solver.exit.assert_called_once()

    # Failure while reading the newly allocated solver's converter also cleans up.
    class BrokenSolver:
        exit = Mock()

        @property
        def converter(self):
            raise RuntimeError("converter failure")

    broken = BrokenSolver()
    monkeypatch.setattr(mgr.env.factory, "Solver", Mock(return_value=broken))
    with pytest.raises(RuntimeError, match="converter failure"):
        NormalizerWalker(mgr.env)
    broken.exit.assert_called_once()
    monkeypatch.setattr(mgr.env.factory, "Solver", Mock(side_effect=RuntimeError("allocation failure")))
    with pytest.raises(RuntimeError, match="allocation failure"):
        TheoryCompilation(mgr.TRUE(), env=mgr.env)


def test_d4_failure_diagnostics_and_cleanup(mgr, monkeypatch):
    import tddnnf.compilers.d4 as d4

    observed = []

    def fail(cmd, **kwargs):
        circuit = Path(cmd[cmd.index("-i") + 1])
        assert circuit.exists()
        observed.append(circuit.parent)
        return subprocess.CompletedProcess(cmd, 23, b"stdout", b"native diagnostic")

    monkeypatch.setattr(d4.subprocess, "run", fail)
    with TheoryCompilation(mgr.Symbol("a"), env=mgr.env) as compilation:
        with pytest.raises(RuntimeError, match=r"exit 23.*\n.*native diagnostic"):
            compilation.compile_treduced(D4Compiler(), [])
    assert observed and all(not path.exists() for path in observed)


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
def test_backend_requires_prepared_abstraction(mgr, backend):
    abstractor = Abstractor()
    with pytest.raises(AssertionError, match="prepared"):
        backend().compile(mgr.Symbol("a"), abstractor)
    assert abstractor.var_count == 0


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("value", [True, False])
def test_compound_constants_and_lemmas(mgr, backend, strategy, value):
    phi = mgr.Or(mgr.Bool(value), mgr.FALSE())
    lemmas = [mgr.TRUE(), mgr.Bool(value)]
    expected = value if strategy == "compile_treduced" else True
    with TheoryCompilation(phi, env=mgr.env) as compilation:
        target = getattr(compilation, strategy)(backend(), lemmas)
    equivalent(mgr, target.to_pysmt(mgr), mgr.Bool(expected))
    assert target.projection_atoms == []


@pytest.mark.parametrize("value", ["typo", ""])
def test_sdd_rejects_invalid_vtree_type(value):
    with pytest.raises(ValueError, match="vtree_type"):
        SddCompiler(vtree_type=value)


@pytest.mark.parametrize("vtree_type", ["right", "left", "vertical", "balanced", "random"])
def test_sdd_supported_vtree_types(mgr, vtree_type):
    phi = mgr.And(mgr.Symbol("a"), mgr.Symbol("b"))
    with TheoryCompilation(phi, env=mgr.env) as compilation:
        target = compilation.compile_treduced(SddCompiler(vtree_type=vtree_type), [])
    equivalent(mgr, target.to_pysmt(mgr), phi)
