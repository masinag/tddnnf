"""Read-only container bindings and retained roots after native reorganization."""

import gc

import pytest

from tddnnf import TheoryCompilation, TheoryCompiledTarget
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tests.support import equivalent


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
