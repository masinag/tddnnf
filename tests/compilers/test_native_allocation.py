"""Native allocation depends on needed atoms, not sparse abstraction IDs."""

import pytest

from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tests.support import equivalent


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


@pytest.mark.parametrize("compiler", [SddCompiler, D4Compiler])
@pytest.mark.parametrize("project", [False, True], ids=["empty-projection", "nonempty-projection"])
@pytest.mark.parametrize("shape", ["sat", "unsat"])
def test_full_mapping_on_constant_return_paths(mgr, a, b, c, compiler, project, shape):
    abstr = Abstractor({3: a, 7: b, 11: c})
    formula = a if shape == "sat" else mgr.And(a, mgr.Not(a))
    projection = [b] if project else []

    native = compiler().compile(formula, abstr, project_on=projection)

    assert set(native.remapping) == {abstr.get_id(atom) for atom in formula.get_atoms() | set(projection)}
    equivalent(mgr, native.to_pysmt(abstr, mgr), mgr.Bool(shape == "sat"))


@pytest.mark.parametrize("compiler", [SddCompiler, D4Compiler])
def test_full_mapping(mgr, compiler):
    a, forgotten, absent, unrelated = [mgr.Symbol(name) for name in ("a", "forgotten", "absent", "unrelated")]
    abstr = Abstractor({7: forgotten, 1000: a, 2000: absent, 3000: unrelated})
    native = compiler().compile(mgr.And(a, forgotten), abstr, project_on=[absent, a])
    expected_mapping = {7: 1, 1000: 2, 2000: 3} if compiler is SddCompiler else {1000: 1, 2000: 2, 7: 3}
    assert native.remapping == expected_mapping
    if compiler is D4Compiler:
        assert native.var_count == 2
    else:
        assert native.manager.var_count() == 3
    equivalent(mgr, native.to_pysmt(abstr, mgr), a)
