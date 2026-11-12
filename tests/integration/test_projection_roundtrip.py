"""Projected targets remain queryable after compilation and persistence."""

import pytest
from pysmt.environment import Environment

from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries import DdnnifeEngine, SddEngine


def test_cleaned_d4_query_counts(mgr, a, b, c, monkeypatch):
    forgotten = mgr.Symbol("forgotten")
    abstr = Abstractor({3: a, 7: b, 11: c, 15: forgotten})
    formula = mgr.And(a, mgr.Not(c), forgotten)
    projection = [c, b, a]
    raw = "a 1 0\nt 2 0\nt 3 0\n1 2 1 -3 4 -9 0\n1 3 9 -12 0\n"

    def run_d4(circuit_path, out_path):
        out_path.write_text(raw)

    monkeypatch.setattr(D4Compiler, "_run_d4", staticmethod(run_d4))

    native = D4Compiler().compile(formula, abstr, project_on=projection)
    container = TheoryCompiledTarget(native, abstr, projection, env=mgr.env)
    with container.queries(DdnnifeEngine) as queries:
        assert queries.count_truth_assignments() == 2
        assert queries.count_truth_assignments([b]) == queries.count_truth_assignments([mgr.Not(b)]) == 1
        assert queries.count_truth_assignments([mgr.Not(a)]) == 0


@pytest.mark.parametrize("compiler,engine", [(SddCompiler, SddEngine), (D4Compiler, DdnnifeEngine)])
def test_full_mapping_roundtrip_queries(mgr, tmp_path, compiler, engine):
    a, forgotten, absent, unrelated = [mgr.Symbol(name) for name in ("a", "forgotten", "absent", "unrelated")]
    abstr = Abstractor({7: forgotten, 1000: a, 2000: absent, 3000: unrelated})
    native = compiler().compile(mgr.And(a, forgotten), abstr, project_on=[absent, a])
    target = TheoryCompiledTarget(native, abstr, [absent, a], env=mgr.env)
    path = tmp_path / "full-mapping"
    target.save(path)
    loaded = TheoryCompiledTarget.load(path, type(native), env=Environment())
    for container in (target, loaded):
        fm = container.env.formula_manager
        a, absent = fm.Symbol("a"), fm.Symbol("absent")
        with container.queries(engine) as query:
            models = list(query.enumerate_truth_assignments())
            assert len(models) == len({frozenset(m.items()) for m in models}) == 2
            assert {frozenset(m.items()) for m in models} == {
                frozenset({a: True, absent: True}.items()),
                frozenset({a: True, absent: False}.items()),
            }
            assert query.count_truth_assignments() == 2
            assert query.count_truth_assignments([absent]) == 1
            assert query.count_truth_assignments([fm.Not(absent)]) == 1
            assert query.count_truth_assignments([fm.Not(a)]) == 0
