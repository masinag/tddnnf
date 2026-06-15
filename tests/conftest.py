import pytest
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.typing import BOOL, INT, REAL

from tddnnf.core.abstraction import Abstractor
from tests.formula_bank import FORMULA_BANK


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


def shannon_forget(mgr: FormulaManager, formula: FNode, vars_to_forget: list[FNode]) -> FNode:
    current = formula
    sub = mgr.env.substituter
    for var in vars_to_forget:
        f_true = sub.substitute(current, {var: mgr.TRUE()}).simplify()
        f_false = sub.substitute(current, {var: mgr.FALSE()}).simplify()
        current = mgr.Or(f_true, f_false)
    return current.simplify()


class SolverGroundTruth:
    def __init__(self, mgr: FormulaManager, formula: FNode, all_vars: list[FNode], strategy: str) -> None:
        self.original_formula = formula
        self.all_vars = all_vars
        n = len(all_vars)
        if strategy == "all" or n < 3:
            self.project_on = all_vars
        elif strategy == "first_k":
            self.project_on = all_vars[: n // 2]
        elif strategy == "high_ids":
            self.project_on = all_vars[n // 2 :]
        elif strategy == "even":
            self.project_on = all_vars[::2]
        elif strategy == "odd":
            self.project_on = all_vars[1::2]
        else:
            msg = f"unknown strategy: {strategy}"
            raise ValueError(msg)

        self.vars_to_forget = [v for v in all_vars if v not in self.project_on]
        self.expected_formula = shannon_forget(mgr, formula, self.vars_to_forget)


@pytest.fixture(params=FORMULA_BANK)
def bank_case(request: pytest.FixtureRequest, mgr: FormulaManager, abstr: Abstractor) -> SolverGroundTruth:
    gen_fn, num_vars, strategy = request.param
    v = [mgr.Symbol(f"v{gen_fn.__name__}_{i}", BOOL) for i in range(num_vars)]
    for var in v:
        abstr.get_id(var)
    formula = gen_fn(mgr, v)
    return SolverGroundTruth(mgr, formula, v, strategy)
