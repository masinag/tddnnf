"""Targets retain read-only context bindings after compilation ends."""

import gc

import ddnnife
import pytest
from pysmt.environment import Environment

from tddnnf import TheoryCompilation
from tddnnf.builders.extended import TExtendedBuilder
from tddnnf.builders.reduced import TReducedBuilder
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4CompiledTarget, D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries.bdd_engine import BddEngine
from tddnnf.queries.ddnnife_engine import DdnnifeEngine
from tddnnf.queries.sdd_engine import SddEngine
from tests.test_compilation_pipeline import equivalent


@pytest.mark.parametrize("backend", [BddCompiler, SddCompiler, D4Compiler])
@pytest.mark.parametrize("shape", ["true", "false", "shared"])
def test_bound_target_survives_compilation_and_gc(mgr, backend, shape):
    a, b, c = [mgr.Symbol(name) for name in ("a", "b", "c")]
    shared = mgr.Or(a, b)
    phi = {"true": mgr.TRUE(), "false": mgr.FALSE(), "shared": mgr.Iff(shared, mgr.And(shared, c))}[shape]
    with TheoryCompilation(phi, env=mgr.env) as compilation:
        target = compilation.compile_treduced(backend(), [])
    del compilation
    gc.collect()
    with Environment():
        reconstructed = target.to_pysmt()
        assert reconstructed in mgr.formulae.values()
    equivalent(mgr, reconstructed, phi)
    assert target.env is mgr.env
    if backend is D4Compiler and shape != "shared":
        # ddnnife 0.10 rejects zero-feature files; delegation preserves that limitation.
        with pytest.raises(ddnnife.InternalError, match="fixedbitset size 0"):
            target.dag_size()
    else:
        assert target.dag_size() == target.target.dag_size()


@pytest.mark.parametrize("backend", [BddCompiler, SddCompiler, D4Compiler])
def test_constructor_inputs_are_copied_and_state_is_read_only(mgr, backend):
    a, b = mgr.Symbol("a"), mgr.Symbol("b")
    mapping = {3: a}
    abstr = Abstractor(mapping)
    projection = [a]
    representation = backend().compile(a, abstr, project_on=projection)
    target = TheoryCompiledTarget(representation, abstr, projection, env=mgr.env)
    mapping[3] = b
    projection.append(b)
    assert target.projection_atoms == (a,)
    assert abstr.get_atom(3) is a
    assert dict(abstr.atom_to_id) == {a: 3}
    for field, value in [("target", representation), ("abstr", abstr), ("env", mgr.env), ("projection_atoms", ())]:
        with pytest.raises(AttributeError):
            setattr(target, field, value)
    with pytest.raises(TypeError):
        abstr.id_to_atom[3] = b
    with pytest.raises(TypeError):
        abstr.atom_to_id[b] = 4
    with pytest.raises(TypeError):
        target.projection_atoms[0] = b
    equivalent(mgr, target.to_pysmt(), a)


def test_d4_remapping_is_copied_and_read_only():
    mapping = {7: 1}
    target = D4CompiledTarget("t 1\n", 1, mapping)
    mapping[7] = 2
    assert dict(target.remapping) == {7: 1}
    with pytest.raises(TypeError):
        target.remapping[7] = 3


@pytest.mark.parametrize("backend", [BddCompiler, SddCompiler])
def test_native_reorganization_preserves_retained_root(mgr, backend):
    a, b, c, d = [mgr.Symbol(name) for name in ("a", "b", "c", "d")]
    phi = mgr.Iff(mgr.Or(a, b), mgr.And(c, d))
    with TheoryCompilation(phi, env=mgr.env) as compilation:
        target = compilation.compile_treduced(backend(), [])
    gc.collect()
    manager = target.target.manager
    if backend is BddCompiler:
        manager.reorder({"b1": 3, "b2": 2, "b3": 1, "b4": 0})
    else:
        manager.minimize()
        manager.garbage_collect()
    equivalent(mgr, target.to_pysmt(), phi)


@pytest.mark.parametrize("backend", [BddCompiler, SddCompiler, D4Compiler])
@pytest.mark.parametrize("builder_name", ["reduced", "extended"])
def test_shared_abstraction_growth_preserves_earlier_target(mgr, backend, builder_name):
    a, b, c, d = [mgr.Symbol(name) for name in ("a", "b", "c", "d")]
    abstr = Abstractor()
    builder_cls = TReducedBuilder if builder_name == "reduced" else TExtendedBuilder
    builder = builder_cls(backend(), env=mgr.env)
    first = builder.build(mgr.Or(a, b), [], abstr, [a, b])
    engine_cls = {BddCompiler: BddEngine, SddCompiler: SddEngine, D4Compiler: DdnnifeEngine}[backend]
    engine = engine_cls(first)

    def check_first(query):
        assert query.count_truth_assignments() == 3
        assert query.count_truth_assignments([a]) == 2
        assert query.count_truth_assignments([mgr.Not(a)]) == 1
        assert query.count_truth_assignments([a, a]) == 2
        assert query.count_truth_assignments([a, mgr.Not(a)]) == 0
        assert not query.is_satisfiable([mgr.Not(a), mgr.Not(b)])
        assert query.is_satisfiable([a])
        assert query.entails_clause([a, b])
        assert query.is_implicant([a])
        models = list(query.enumerate_truth_assignments())
        assert len(models) == 3
        assert {frozenset(model.items()) for model in models} == {
            frozenset({a: True, b: True}.items()),
            frozenset({a: True, b: False}.items()),
            frozenset({a: False, b: True}.items()),
        }
        equivalent(mgr, first.to_pysmt(), mgr.Or(a, b))

    check_first(engine)
    second = builder.build(mgr.And(c, d), [], abstr, [d, c])
    assert first.abstr is second.abstr is abstr
    assert dict(abstr.id_to_atom) == {1: a, 2: b, 3: d, 4: c}
    assert first.projection_atoms == (a, b)
    assert second.projection_atoms == (d, c)
    equivalent(mgr, second.to_pysmt(), mgr.And(c, d))
    assert engine_cls(second).count_truth_assignments() == 1
    check_first(engine)
    check_first(engine_cls(first))
    with pytest.raises(ValueError, match="projection atom"):
        engine.count_truth_assignments([c])
