"""Direct compiler configuration and prepared abstraction requirements."""

import pytest
from pysdd.sdd import SddManager, Vtree

from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tests.support import BACKENDS, equivalent


@pytest.mark.parametrize("options", [{}, {"auto_gc_and_minimize": True}, {"auto_gc_and_minimize": False}])
def test_sdd_native_options(mgr, options):
    compiler = SddCompiler(vtree_type="right", **options)
    # Compare actual native configuration and vtree with native construction.
    a, b, c = [mgr.Symbol(name) for name in ("a", "b", "c")]
    phi = mgr.And(mgr.Or(a, b), c)
    abstr = Abstractor({1: a, 2: b, 3: c})
    target = compiler.compile(phi, abstr)
    manager = target.manager
    assert bool(manager.is_auto_gc_and_minimize_on()) is options.get("auto_gc_and_minimize", True)
    expected = SddManager.from_vtree(Vtree(var_count=3, vtree_type="right"))
    assert manager.vtree().left().is_leaf() == expected.vtree().left().is_leaf()
    equivalent(mgr, target.to_pysmt(abstr, mgr), phi)


@pytest.mark.parametrize("backend", BACKENDS)
def test_backend_requires_prepared_abstraction(mgr, backend):
    abstractor = Abstractor()
    with pytest.raises(AssertionError, match="prepared"):
        backend().compile(mgr.Symbol("a"), abstractor)
    assert abstractor.var_count == 0


@pytest.mark.parametrize("value", ["typo", ""])
def test_sdd_rejects_invalid_vtree_type(value):
    with pytest.raises(ValueError, match="vtree_type"):
        SddCompiler(vtree_type=value)


@pytest.mark.parametrize("vtree_type", ["right", "left", "vertical", "balanced", "random"])
def test_sdd_supported_vtree_types(mgr, vtree_type):
    phi = mgr.And(mgr.Symbol("a"), mgr.Symbol("b"))
    abstr = Abstractor({1: mgr.Symbol("a"), 2: mgr.Symbol("b")})
    target = SddCompiler(vtree_type=vtree_type).compile(phi, abstr)
    equivalent(mgr, target.to_pysmt(abstr, mgr), phi)
