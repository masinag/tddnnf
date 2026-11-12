"""Native allocation depends on needed atoms, not sparse abstraction IDs."""

import pytest
from pysmt.environment import Environment

from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries import DdnnifeEngine, SddEngine


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


@pytest.mark.parametrize("compiler,engine", [(SddCompiler, SddEngine), (D4Compiler, DdnnifeEngine)])
def test_full_mapping_and_roundtrip(mgr, tmp_path, compiler, engine):
    a, forgotten, absent, unrelated = [mgr.Symbol(name) for name in ("a", "forgotten", "absent", "unrelated")]
    abstr = Abstractor({7: forgotten, 1000: a, 2000: absent, 3000: unrelated})
    native = compiler().compile(mgr.And(a, forgotten), abstr, project_on=[absent, a])
    expected_mapping = {7: 1, 1000: 2, 2000: 3} if compiler is SddCompiler else {1000: 1, 2000: 2, 7: 3}
    assert native.remapping == expected_mapping
    if compiler is D4Compiler:
        assert native.var_count == 2
    target = TheoryCompiledTarget(native, abstr, [absent, a], env=mgr.env)
    path = tmp_path / "full-mapping"
    target.save(path)
    loaded = TheoryCompiledTarget.load(path, type(native), env=Environment())
    assert loaded.target.remapping == expected_mapping
    for container in (target, loaded):
        fm = container.env.formula_manager
        a, absent = fm.Symbol("a"), fm.Symbol("absent")
        with container.env.factory.Solver() as solver:
            solver.add_assertion(fm.Not(fm.Iff(container.to_pysmt(), a)))
            assert not solver.solve()
        with container.queries(engine) as query:
            models = list(query.enumerate_truth_assignments())
            assert len(models) == 2
            assert {frozenset(m.items()) for m in models} == {
                frozenset({a: True, absent: True}.items()),
                frozenset({a: True, absent: False}.items()),
            }
            assert query.count_truth_assignments() == 2
            assert query.count_truth_assignments([absent]) == 1
            assert query.count_truth_assignments([fm.Not(absent)]) == 1
            assert query.count_truth_assignments([fm.Not(a)]) == 0
