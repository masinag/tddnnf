"""Shared formula, environment, backend, and solver-bank fixtures."""

import pytest
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.typing import BOOL, INT, REAL

from tddnnf.core.abstraction import Abstractor
from tests.formula_bank import FORMULA_BANK
from tests.support import PAIRINGS, SolverGroundTruth


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


@pytest.fixture(params=FORMULA_BANK, ids=[f"{fn.__name__}-{n}-{strategy}" for fn, n, strategy in FORMULA_BANK])
def bank_case(request: pytest.FixtureRequest, mgr: FormulaManager) -> SolverGroundTruth:
    gen_fn, num_vars, strategy = request.param
    v = [mgr.Symbol(f"v{gen_fn.__name__}_{i}", BOOL) for i in range(num_vars)]
    formula = gen_fn(mgr, v)
    return SolverGroundTruth(mgr, formula, v, strategy)


@pytest.fixture(params=PAIRINGS, ids=["cudd", "sdd", "ddnnife"])
def pairing(request):
    return request.param


@pytest.fixture
def compiler(pairing):
    return pairing[0]()


def evaluate(mgr, formula, assignment):
    result = mgr.env.substituter.substitute(formula, {atom: mgr.Bool(value) for atom, value in assignment.items()})
    result = mgr.env.simplifier.simplify(result)
    assert result.is_bool_constant()
    return result.is_true()
