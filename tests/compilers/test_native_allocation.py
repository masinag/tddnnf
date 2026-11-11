"""Native allocation depends on needed atoms, not sparse abstraction IDs."""

import pytest

from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor


def test_sdd_allocates_only_needed_variables(mgr, a, b, c):
    unused = mgr.Symbol("unused")
    abstr = Abstractor({7: a, 1000: b, 2000: c, 3000: unused})

    target = SddCompiler().compile(mgr.And(a, b), abstr, project_on=[a, c])

    assert target.manager.var_count() == 3


def test_bdd_allocates_only_needed_variables(mgr, a, b, c):
    unused = mgr.Symbol("unused")
    abstr = Abstractor({7: a, 1000: b, 2000: c, 3000: unused})

    target = BddCompiler().compile(mgr.And(a, b), abstr, project_on=[a, c])

    assert len(target.manager.vars) == 3


@pytest.mark.parametrize("value", [False, True])
def test_sdd_constant_allocates_one_required_native_variable(mgr, value):
    abstr = Abstractor({1000: mgr.Symbol("unused")})

    target = SddCompiler().compile(mgr.Bool(value), abstr, project_on=[])

    assert target.manager.var_count() == 1


@pytest.mark.parametrize("value", [False, True])
def test_bdd_constant_allocates_no_variables(mgr, value):
    abstr = Abstractor({1000: mgr.Symbol("unused")})

    target = BddCompiler().compile(mgr.Bool(value), abstr, project_on=[])

    assert not target.manager.vars
