"""ddnnife constants, mapping validation, absent projection atoms, and native zero-feature failures."""

import ddnnife
import pytest

from tddnnf.compilers.d4 import D4CompiledTarget, D4Compiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries.ddnnife_engine import DdnnifeEngine
from tests.support import PAIRINGS, compile_target


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
        assert engine.entails_clause([mgr.TRUE()])
        assert engine.is_implicant([mgr.TRUE()])
        assert {frozenset(m.items()) for m in engine.enumerate_truth_assignments()} == {
            frozenset({a: True}.items()),
            frozenset({a: False}.items()),
        }
    finally:
        engine.close()


def test_ddnnife_rejects_partial_mapping(mgr, a, b):
    abstr = Abstractor({3: a, 7: b})
    native = D4CompiledTarget("o 1 0\nt 2 0\n1 2 1 0\n", 2, {3: 1})
    target = TheoryCompiledTarget(native, abstr, [a, b], env=mgr.env)
    with pytest.raises(AssertionError, match="D4 mapping"):
        DdnnifeEngine(target)


def test_ddnnife_absent_atom_is_mapped(mgr, a, b):
    target = compile_target(mgr, PAIRINGS[2], a, [a, b])
    assert target.abstr.get_id(b) in target.target.remapping
    q = DdnnifeEngine(target)
    try:
        assert q.count_truth_assignments() == 2
        assert q.count_truth_assignments([b]) == 1
        assert not q.is_satisfiable([b, mgr.Not(b)])
        assert len(list(q.enumerate_truth_assignments())) == 2
    finally:
        q.close()
