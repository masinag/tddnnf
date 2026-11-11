"""Native targets default to identity mappings and retain explicit mappings."""

import pytest
from pysdd.sdd import SddManager

from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.compilers.pysdd import SddCompiledTarget
from tddnnf.core.abstraction import Abstractor
from tests.support import equivalent


@pytest.mark.parametrize("kwargs", [{}, {"remapping": None}, {"remapping": {}}], ids=["omitted", "none", "empty"])
def test_d4_default_mapping_reconstructs_native_literals(mgr, a, b, kwargs):
    target = D4CompiledTarget("a 1 0\nt 2 0\n1 2 1 -2 0\n", 2, **kwargs)
    abstr = Abstractor({1: a, 2: b})

    equivalent(mgr, target.to_pysmt(abstr, mgr), mgr.And(a, mgr.Not(b)))


@pytest.mark.parametrize("kwargs", [{}, {"remapping": None}, {"remapping": {}}], ids=["omitted", "none", "empty"])
def test_sdd_default_mapping_reconstructs_native_literals(mgr, a, b, kwargs):
    manager = SddManager(var_count=2)
    target = SddCompiledTarget(manager.literal(1) & manager.literal(-2), manager, **kwargs)
    abstr = Abstractor({1: a, 2: b})

    equivalent(mgr, target.to_pysmt(abstr, mgr), mgr.And(a, mgr.Not(b)))


def test_sdd_explicit_mapping_is_copied_and_read_only():
    manager = SddManager(var_count=2)
    mapping = {7: 1}
    target = SddCompiledTarget(manager.literal(1), manager, mapping)

    mapping[7] = 2

    assert dict(target.remapping) == {7: 1}
    with pytest.raises(TypeError):
        target.remapping[7] = 2


def test_d4_zero_variables_have_empty_mapping():
    assert dict(D4CompiledTarget("t 1\n", 0).remapping) == {}
