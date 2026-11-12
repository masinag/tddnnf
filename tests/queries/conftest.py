"""Local direct-engine construction and guaranteed teardown."""

import pytest
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import PropCompiler, QueryEngine


@pytest.fixture
def engine_factory(pairing):
    opened = []

    def create(target):
        engine = pairing[1](target)
        opened.append(engine)
        return engine

    yield create
    for engine in reversed(opened):
        engine.close()


@pytest.fixture
def engine(compiler: PropCompiler, mgr: FormulaManager, a: FNode, b: FNode, engine_factory) -> QueryEngine:
    abstr = Abstractor({1: a, 2: b})
    target = compiler.compile(mgr.And(a, b), abstr)
    return engine_factory(TheoryCompiledTarget(target, abstr, projection_atoms=[a, b], env=mgr.env))
