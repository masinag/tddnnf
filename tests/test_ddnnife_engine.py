import ddnnife
import pytest

from tddnnf.compilers.d4 import D4CompiledTarget, D4Compiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries.ddnnife_engine import DdnnifeEngine
from tests._base_engine_test import BaseTestEngine


class TestDdnnifeEngine(BaseTestEngine[D4CompiledTarget]):
    compiler_cls = D4Compiler
    engine_cls = DdnnifeEngine


@pytest.mark.parametrize("truth", [False, True])
@pytest.mark.parametrize("active", [False, True])
def test_constant_targets(mgr, a, truth, active):
    projection = [a] if active else []
    abstr = Abstractor({1: a})
    native = D4Compiler().compile(mgr.Bool(truth), abstr, project_on=projection)
    container = TheoryCompiledTarget(native, abstr, projection, env=mgr.env)
    if not truth or not active:
        with pytest.raises(ddnnife.InternalError):
            DdnnifeEngine(container)
        return
    engine = DdnnifeEngine(container)
    try:
        assert engine.is_satisfiable()
        assert engine.is_valid()
        assert engine.count_truth_assignments() == 2
        assert engine.count_truth_assignments([a]) == 1
        assert engine.entails_clause(mgr.TRUE())
        assert engine.is_implicant(mgr.TRUE())
        assert {frozenset(m.items()) for m in engine.enumerate_truth_assignments()} == {
            frozenset({a: True}.items()),
            frozenset({a: False}.items()),
        }
    finally:
        engine.close()
