import pytest
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.typing import BOOL, INT, REAL

from tddnnf.core.abstraction import Abstractor


@pytest.fixture
def env() -> Environment:
    return Environment()


@pytest.fixture
def mgr(env) -> FormulaManager:
    return env.formula_manager


@pytest.fixture
def abstr() -> Abstractor:
    return Abstractor()


@pytest.fixture
def x(mgr) -> FNode:
    return mgr.Symbol("x", INT)


@pytest.fixture
def y_int(mgr) -> FNode:
    return mgr.Symbol("y", INT)


@pytest.fixture
def y_real(mgr) -> FNode:
    return mgr.Symbol("y", REAL)


@pytest.fixture
def p(mgr) -> FNode:
    return mgr.Symbol("p", BOOL)


@pytest.fixture
def a(mgr) -> FNode:
    return mgr.Symbol("a", BOOL)


@pytest.fixture
def b(mgr) -> FNode:
    return mgr.Symbol("b", BOOL)


@pytest.fixture
def c(mgr) -> FNode:
    return mgr.Symbol("c", BOOL)
