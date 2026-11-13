"""Check single-kind quantification against independent Boolean truth tables."""

from itertools import product
from unittest.mock import Mock

import pytest

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiledTarget, BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.pysmt_utils import compilation_vocabulary
from tddnnf.queries import BddEngine, SddEngine

BACKENDS = [BddCompiler, SddCompiler, D4Compiler]


def evaluate(mgr, formula, assignment):
    result = mgr.env.substituter.substitute(formula, {atom: mgr.Bool(value) for atom, value in assignment.items()})
    result = mgr.env.simplifier.simplify(result)
    assert result.is_bool_constant()
    return result.is_true()


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("quantifiers", [([], []), (["e"], []), ([], ["u"]), (["e", "a"], []), ([], ["u", "e"])])
@pytest.mark.parametrize("shape", ["iff", "free", "guarded", "true", "false"])
@pytest.mark.parametrize("absent_free", [False, True])
def test_boolean_truth_tables(mgr, backend, quantifiers, shape, absent_free, monkeypatch):
    atoms = {name: mgr.Symbol(name) for name in ("a", "e", "u", "absent")}
    a, e, u = (atoms[name] for name in ("a", "e", "u"))
    formula = {
        "iff": mgr.Iff(e, u),
        "free": mgr.Iff(a, mgr.Iff(e, u)),
        "guarded": mgr.Or(a, mgr.Iff(e, u)),
        "true": mgr.TRUE(),
        "false": mgr.FALSE(),
    }[shape]
    boolean = {
        "iff": lambda v: v[e] == v[u],
        "free": lambda v: v[a] == (v[e] == v[u]),
        "guarded": lambda v: v[a] or v[e] == v[u],
        "true": lambda v: True,
        "false": lambda v: False,
    }[shape]
    all_vars = [atoms[name] for name in (("absent", "u", "a", "e") if absent_free else ("u", "a", "e"))]
    exists, forall = ([atoms[name] for name in group] for group in quantifiers)
    retained = [atom for atom in all_vars if atom not in exists + forall]
    assert compilation_vocabulary(formula, all_vars, exists, forall) == tuple(retained)
    abstraction = Abstractor({7 + 11 * i: atom for i, atom in enumerate(all_vars)})
    compiler = backend()
    if backend is D4Compiler and forall:
        run = Mock(side_effect=AssertionError("External compiler must not run"))
        monkeypatch.setattr(compiler, "_run_d4", run)
        with pytest.raises(NotImplementedError, match="universal"):
            compiler.compile(formula, abstraction, all_vars=all_vars, exists_vars=exists, forall_vars=forall)
        run.assert_not_called()
        return
    target = compiler.compile(formula, abstraction, all_vars=all_vars, exists_vars=exists, forall_vars=forall)
    actual = target.to_pysmt(abstraction, mgr)
    assert actual.get_atoms() <= set(retained)
    for free_values in product((False, True), repeat=len(retained)):
        free = dict(zip(retained, free_values))
        quantified = exists or forall
        expected = (any if exists else all)(
            boolean(free | dict(zip(quantified, values))) for values in product((False, True), repeat=len(quantified))
        )
        assert evaluate(mgr, actual, free) == expected


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "exists_outside",
        "forall_outside",
        "overlap",
        "mixed",
        "compound",
        "constant",
        "duplicate",
        "duplicate_exists",
        "negative",
        "non_node",
    ],
)
def test_invalid_declarations(mgr, backend, case, monkeypatch):
    a, b = mgr.Symbol("a"), mgr.Symbol("b")
    declarations = {
        "missing": ([b], [], []),
        "exists_outside": ([a], [b], []),
        "forall_outside": ([a], [], [b]),
        "overlap": ([a], [a], [a]),
        "mixed": ([a, b], [a], [b]),
        "compound": ([a, mgr.And(a, b)], [], []),
        "constant": ([a, mgr.TRUE()], [], []),
        "duplicate": ([a, a], [], []),
        "duplicate_exists": ([a], [a, a], []),
        "negative": ([a], [], [mgr.Not(a)]),
        "non_node": ([a, "b"], [], []),
    }
    all_vars, exists, forall = declarations[case]
    compiler = backend()
    if backend is D4Compiler:
        monkeypatch.setattr(compiler, "_run_d4", Mock(side_effect=AssertionError("Must validate first")))
    with pytest.raises(ValueError):
        compiler.compile(a, Abstractor({1: a, 2: b}), all_vars=all_vars, exists_vars=exists, forall_vars=forall)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("truth", [False, True])
def test_empty_vocabulary(mgr, backend, truth):
    target = backend().compile(mgr.Bool(truth), Abstractor(), all_vars=[])
    assert evaluate(mgr, target.to_pysmt(Abstractor(), mgr), {}) == truth


@pytest.mark.parametrize("backend", BACKENDS)
def test_all_dimensions_quantified(mgr, backend):
    e, u = mgr.Symbol("e"), mgr.Symbol("u")
    abstraction = Abstractor({3: e, 90: u})
    universal = [] if backend is D4Compiler else [e, u]
    existential = [e, u] if backend is D4Compiler else []
    target = backend().compile(
        mgr.Iff(e, u), abstraction, all_vars=[u, e], exists_vars=existential, forall_vars=universal
    )
    assert evaluate(mgr, target.to_pysmt(abstraction, mgr), {}) == (backend is D4Compiler)


@pytest.mark.parametrize(
    "backend,target_type,engine",
    [(BddCompiler, BddCompiledTarget, BddEngine), (SddCompiler, SddCompiledTarget, SddEngine)],
)
def test_extended_generated_atom_roundtrip(mgr, tmp_path, backend, target_type, engine):
    p, w = mgr.Symbol("p"), mgr.Symbol("generated")
    phi = p
    lemma = mgr.Iff(p, w)
    with TheoryCompilation(phi, all_vars=[p], env=mgr.env) as compilation:
        target = compilation.compile_textended(backend(), [lemma])
    path = tmp_path / "compiled"
    target.save(path)
    loaded = TheoryCompiledTarget.load(path, target_type, env=mgr.env)
    for artifact in (target, loaded):
        assert artifact.projection_atoms == (p,)
        for value in (False, True):
            assert evaluate(mgr, artifact.to_pysmt(), {p: value}) == value
        with artifact.queries(engine) as queries:
            assert not queries.is_valid()
            assert queries.is_implicant(p)
            assert not queries.is_implicant(mgr.Not(p))
            assert not queries.is_implicant(mgr.TRUE())
            assert queries.count_truth_assignments() == 1
