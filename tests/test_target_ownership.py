"""Targets retain their own immutable context after compilation ends."""

import gc
from dataclasses import FrozenInstanceError

import pytest
from pysmt.environment import Environment

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiledTarget, BddCompiler, _BddRepresentation
from tddnnf.compilers.d4 import D4CompiledTarget, D4Compiler, _D4Representation
from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler, _SddRepresentation
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
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
        import ddnnife

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
        with pytest.raises(FrozenInstanceError):
            setattr(target, field, value)
    with pytest.raises(FrozenInstanceError):
        abstr._id_to_atom = {}
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


def test_transitional_backend_aliases():
    assert BddCompiledTarget is _BddRepresentation
    assert SddCompiledTarget is _SddRepresentation
    assert D4CompiledTarget is _D4Representation
