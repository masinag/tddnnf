"""Session projection vocabulary survives sparse abstraction growth."""

import pytest
from pysmt.typing import BOOL

from tddnnf import TheoryCompiledTarget
from tddnnf.core.abstraction import Abstractor


def test_sparse_projection_growth(mgr, a, b, c, pairing):
    forgotten = mgr.Symbol("forgotten", BOOL)
    abstr = Abstractor({3: a, 7: b, 11: c, 15: forgotten})
    native = pairing[0]().compile(mgr.And(a, forgotten), abstr, project_on=[c, b, a])
    target = TheoryCompiledTarget(native, abstr, [c, b, a], env=mgr.env)
    with target.queries(pairing[1]) as q:
        abstr.get_id(mgr.Symbol("later", BOOL))
        assert q.count_truth_assignments() == 4
        assert q.count_truth_assignments([c, c]) == 2
        assert q.count_truth_assignments([mgr.Not(a)]) == 0
        models = list(q.enumerate_truth_assignments())
        assert len(models) == len({frozenset(m.items()) for m in models}) == 4
        assert all(tuple(m) == (c, b, a) for m in models)
        with pytest.raises(ValueError):
            q.is_satisfiable([forgotten])
