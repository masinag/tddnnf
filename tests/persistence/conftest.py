"""Saved native artifacts used by roundtrip and failure contracts."""

import pytest
from dd.cudd import BDD
from pysdd.sdd import SddManager, Vtree

from tddnnf.compilers.cudd import BddCompiledTarget
from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.compilers.pysdd import SddCompiledTarget
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget


@pytest.fixture(params=["obdd", "sdd", "ddnnf"])
def artifact(request, mgr, tmp_path):
    a, inactive, absent = [mgr.Symbol(name) for name in ("a", "inactive", "absent")]
    abstr = Abstractor({3: a, 7: inactive, 11: absent})
    rep = request.param
    if rep == "obdd":
        manager = BDD()
        manager.declare(*(f"b{i}" for i in range(1, 12)))
        manager.reorder({f"b{i}": 11 - i for i in range(1, 12)})
        native = BddCompiledTarget(manager.var("b3"), manager)
    elif rep == "sdd":
        tree = Vtree(var_count=11, vtree_type="left")
        manager = SddManager.from_vtree(tree)
        manager.auto_gc_and_minimize_off()
        native = SddCompiledTarget(manager.literal(3), manager, {i: i for i in range(1, 12)})
    else:
        native = D4CompiledTarget("o 1 0\nt 2 0\n1 2 1 0\n", 2, {3: 1, 11: 2})
    container = TheoryCompiledTarget(native, abstr, [absent, a], env=mgr.env)
    path = tmp_path / "artifact"
    container.save(path)
    return path, container
