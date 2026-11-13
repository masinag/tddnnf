import pytest

from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries.sdd_engine import SddEngine
from tests._base_engine_test import BaseTestEngine


class TestSddEngine(BaseTestEngine[SddCompiledTarget]):
    compiler_cls = SddCompiler
    engine_cls = SddEngine


@pytest.mark.parametrize("sparse", [False, True])
@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("shape", ["true", "false", "atom"])
def test_count_uses_native_dimensions(mgr, sparse, project, shape):
    a = mgr.Symbol("a")
    abstr = Abstractor({7: a}) if sparse else Abstractor()
    formula = {"true": mgr.TRUE(), "false": mgr.FALSE(), "atom": a}[shape]
    projection = [a] if project else []
    abstr.get_id(a)
    native = SddCompiler().compile(formula, abstr, all_atoms=[a], exists_atoms=[] if project else [a])
    target = TheoryCompiledTarget(native, abstr, projection_atoms=projection, env=mgr.env)
    engine = SddEngine(target)
    expected = 0 if shape == "false" else (2 if project and shape == "true" else 1)
    assert engine.count_truth_assignments() == expected
    if project:
        assert engine.count_truth_assignments([a]) == (0 if shape == "false" else 1)
        assert engine.count_truth_assignments([mgr.Not(a)]) == (1 if shape == "true" else 0)
