import json

import pytest
from pysdd.sdd import SddManager
from pysmt.environment import Environment

from tddnnf import TheoryCompilation, TheoryCompiledTarget
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.queries.bdd_engine import BddEngine
from tddnnf.queries.sdd_engine import SddEngine


@pytest.mark.parametrize("compiler,engine", [(SddCompiler, SddEngine), (BddCompiler, BddEngine)])
@pytest.mark.parametrize("projection", ["a", "absent", "empty"])
def test_sparse_allocation_and_roundtrip(mgr, tmp_path, compiler, engine, projection):
    a, b, absent = [mgr.Symbol(name) for name in ("a", "b", "absent")]
    abstr = Abstractor({7: a, 1000: b, 2000: absent})
    project = {"a": [a], "absent": [absent, a], "empty": []}[projection]
    with TheoryCompilation(mgr.And(a, b), project, env=mgr.env) as compilation:
        target = compilation.compile_treduced(compiler(), [], abstractor=abstr)
    needed = {7, 1000} | ({2000} if projection == "absent" else set())
    if compiler is SddCompiler:
        assert target.target.manager.var_count() == len(needed)
        assert dict(target.target.remapping) == {idx: native for native, idx in enumerate(sorted(needed), 1)}
        with pytest.raises(TypeError):
            target.target.remapping[7] = 9
    else:
        assert set(target.target.manager.vars) == {f"b{idx}" for idx in needed}
    abstr.get_id(mgr.Symbol("later"))
    path = tmp_path / "target"
    target.save(path)
    fresh = Environment()
    loaded = TheoryCompiledTarget.load(path, type(target.target), env=fresh)
    for container in (target, loaded):
        atom = container.env.formula_manager.Symbol("a")
        with container.queries(engine) as query:
            expected = 2 if projection == "absent" else 1
            assert query.count_truth_assignments() == expected
            assert query.is_satisfiable()
            assert query.is_valid() == (projection == "empty")
            if projection != "empty":
                assert query.entails_clause(atom)
                assert query.is_implicant(atom)
                assert query.count_truth_assignments([container.env.formula_manager.Not(atom)]) == 0
            assert len(list(query.enumerate_truth_assignments())) == expected
        formula_manager = container.env.formula_manager
        expected_formula = atom if projection != "empty" else formula_manager.TRUE()
        with container.env.factory.Solver() as solver:
            solver.add_assertion(formula_manager.Not(formula_manager.Iff(container.to_pysmt(), expected_formula)))
            assert not solver.solve()


def test_sdd_requires_mapping(tmp_path):
    manager = SddManager(var_count=1)
    path = tmp_path / "target"
    SddCompiledTarget(manager.true(), manager, {}).save(path)
    metadata = path / "metadata.json"
    data = json.loads(metadata.read_text())
    del data["remapping"]
    metadata.write_text(json.dumps(data))
    with pytest.raises(KeyError, match="remapping"):
        SddCompiledTarget.load(path)


@pytest.mark.parametrize("compiler", [SddCompiler, BddCompiler])
@pytest.mark.parametrize("value", [False, True])
def test_constant_allocation(mgr, compiler, value):
    abstr = Abstractor({1000: mgr.Symbol("unused")})
    target = compiler().compile(mgr.Bool(value), abstr, project_on=[])
    if compiler is SddCompiler:
        assert target.manager.var_count() == 1
        assert dict(target.remapping) == {}
    else:
        assert not target.manager.vars
