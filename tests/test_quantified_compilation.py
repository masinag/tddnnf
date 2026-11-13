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
from tests.conftest import evaluate

BACKENDS = [BddCompiler, SddCompiler, D4Compiler]


BOOLEAN_CASES = [
    pytest.param(lambda m, s: m.Iff(s["e"], s["u"]), lambda v: v["e"] == v["u"], id="iff"),
    pytest.param(lambda m, s: m.Iff(s["a"], m.Iff(s["e"], s["u"])), lambda v: v["a"] == (v["e"] == v["u"]), id="free"),
    pytest.param(lambda m, s: m.Or(s["a"], m.Iff(s["e"], s["u"])), lambda v: v["a"] or v["e"] == v["u"], id="guarded"),
    pytest.param(lambda m, s: m.TRUE(), lambda v: True, id="true"),
    pytest.param(lambda m, s: m.FALSE(), lambda v: False, id="false"),
]

INVALID_DECLARATIONS = [
    pytest.param(lambda m, a, b: ([b], [], []), id="missing"),
    pytest.param(lambda m, a, b: ([a], [b], []), id="exists_outside"),
    pytest.param(lambda m, a, b: ([a], [], [b]), id="forall_outside"),
    pytest.param(lambda m, a, b: ([a], [a], [a]), id="overlap"),
    pytest.param(lambda m, a, b: ([a, b], [a], [b]), id="mixed"),
    pytest.param(lambda m, a, b: ([a, m.And(a, b)], [], []), id="compound"),
    pytest.param(lambda m, a, b: ([a, m.TRUE()], [], []), id="constant"),
    pytest.param(lambda m, a, b: ([a, a], [], []), id="duplicate"),
    pytest.param(lambda m, a, b: ([a], [a, a], []), id="duplicate_exists"),
    pytest.param(lambda m, a, b: ([a], [], [m.Not(a)]), id="negative"),
    pytest.param(lambda m, a, b: ([a, "b"], [], []), id="non_node"),
]


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("quantifiers", [([], []), (["e"], []), ([], ["u"]), (["e", "a"], []), ([], ["u", "e"])])
@pytest.mark.parametrize("formula_builder,boolean", BOOLEAN_CASES)
@pytest.mark.parametrize("absent_free", [False, True])
def test_boolean_truth_tables(mgr, backend, quantifiers, formula_builder, boolean, absent_free, monkeypatch):
    atoms = {name: mgr.Symbol(name) for name in ("a", "e", "u", "absent")}
    formula = formula_builder(mgr, atoms)
    all_atoms = [atoms[name] for name in (("absent", "u", "a", "e") if absent_free else ("u", "a", "e"))]
    exists, forall = ([atoms[name] for name in group] for group in quantifiers)
    retained = [atom for atom in all_atoms if atom not in exists + forall]
    assert compilation_vocabulary(formula, all_atoms, exists, forall) == tuple(retained)
    abstraction = Abstractor({7 + 11 * i: atom for i, atom in enumerate(all_atoms)})
    compiler = backend()
    if backend is D4Compiler and forall:
        run = Mock(side_effect=AssertionError("External compiler must not run"))
        monkeypatch.setattr(compiler, "_run_d4", run)
        with pytest.raises(NotImplementedError, match="universal"):
            compiler.compile(formula, abstraction, all_atoms=all_atoms, exists_atoms=exists, forall_atoms=forall)
        run.assert_not_called()
        return
    target = compiler.compile(formula, abstraction, all_atoms=all_atoms, exists_atoms=exists, forall_atoms=forall)
    actual = target.to_pysmt(abstraction, mgr)
    assert actual.get_atoms() <= set(retained)
    for free_values in product((False, True), repeat=len(retained)):
        free = dict(zip(retained, free_values))
        quantified = exists or forall
        expected = (any if exists else all)(
            boolean({atom.symbol_name(): value for atom, value in (free | dict(zip(quantified, values))).items()})
            for values in product((False, True), repeat=len(quantified))
        )
        assert evaluate(mgr, actual, free) == expected


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("declarations", INVALID_DECLARATIONS)
def test_invalid_declarations(mgr, backend, declarations, monkeypatch):
    a, b = mgr.Symbol("a"), mgr.Symbol("b")
    all_atoms, exists, forall = declarations(mgr, a, b)
    compiler = backend()
    if backend is D4Compiler:
        monkeypatch.setattr(compiler, "_run_d4", Mock(side_effect=AssertionError("Must validate first")))
    with pytest.raises(ValueError):
        compiler.compile(a, Abstractor({1: a, 2: b}), all_atoms=all_atoms, exists_atoms=exists, forall_atoms=forall)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("truth", [False, True])
def test_empty_vocabulary(mgr, backend, truth):
    target = backend().compile(mgr.Bool(truth), Abstractor(), all_atoms=[])
    assert evaluate(mgr, target.to_pysmt(Abstractor(), mgr), {}) == truth


@pytest.mark.parametrize("backend", BACKENDS)
def test_all_dimensions_quantified(mgr, backend):
    e, u = mgr.Symbol("e"), mgr.Symbol("u")
    abstraction = Abstractor({3: e, 90: u})
    universal = [] if backend is D4Compiler else [e, u]
    existential = [e, u] if backend is D4Compiler else []
    target = backend().compile(
        mgr.Iff(e, u), abstraction, all_atoms=[u, e], exists_atoms=existential, forall_atoms=universal
    )
    assert evaluate(mgr, target.to_pysmt(abstraction, mgr), {}) == (backend is D4Compiler)


@pytest.mark.parametrize(
    "backend,target_type",
    [(BddCompiler, BddCompiledTarget), (SddCompiler, SddCompiledTarget)],
)
def test_extended_generated_atom_roundtrip(mgr, tmp_path, backend, target_type):
    p, w = mgr.Symbol("p"), mgr.Symbol("generated")
    phi = p
    lemma = mgr.Iff(p, w)
    with TheoryCompilation(phi, atoms=[p], env=mgr.env) as compilation:
        target = compilation.compile_textended(backend(), [lemma])
    path = tmp_path / "compiled"
    target.save(path)
    loaded = TheoryCompiledTarget.load(path, target_type, env=mgr.env)
    for artifact in (target, loaded):
        assert artifact.projection_atoms == (p,)
        for value in (False, True):
            assert evaluate(mgr, artifact.to_pysmt(), {p: value}) == value
