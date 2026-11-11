"""Direct BDD and SDD enumeration covers sparse IDs, projection order, constants, and retained roots."""

import pytest

from tddnnf import TheoryCompiledTarget
from tddnnf.core.abstraction import Abstractor
from tests.support import PAIRINGS


@pytest.mark.parametrize("pairing", PAIRINGS[:2], ids=["cudd", "sdd"])
@pytest.mark.parametrize("sparse", [False, True])
@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("shape", ["true", "false", "atom"])
def test_projected_enumeration(mgr, a, b, c, pairing, sparse, project, shape):
    abstr = Abstractor({3: a, 7: b, 11: c} if sparse else {1: a, 2: b, 3: c})
    projection = [b, a] if project else []
    formula = {"true": c, "false": mgr.FALSE(), "atom": mgr.And(a, c)}[shape]
    native = pairing[0]().compile(formula, abstr, project_on=projection)
    target = TheoryCompiledTarget(native, abstr, projection, env=mgr.env)
    engine = pairing[1](target)
    root = native.root
    expected = []
    if shape != "false":
        expected = (
            [
                {a: value, b: unused}
                for value in ([False, True] if shape == "true" else [True])
                for unused in [False, True]
            ]
            if project
            else [{}]
        )
    models = list(engine.enumerate_truth_assignments())
    assert {frozenset(model.items()) for model in models} == {frozenset(model.items()) for model in expected}
    assert len(models) == len(expected) == engine.count_truth_assignments()
    assert native.root is root
