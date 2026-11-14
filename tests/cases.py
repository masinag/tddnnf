import pytest
from pysmt.shortcuts import FALSE, TRUE, And, Iff, Implies, Ite, Not, Or, Symbol


def compound_formula():
    p, q, r, s, t = (Symbol(name) for name in ("p", "q", "r", "s", "t"))
    return And(p, Or(q, r), Or(Not(q), s), Or(t, r))


PLAIN_CASES = [
    pytest.param(TRUE, id="true"),
    pytest.param(FALSE, id="false"),
    pytest.param(lambda: Symbol("p"), id="atom"),
    pytest.param(lambda: Not(Symbol("p")), id="negation"),
    pytest.param(lambda: And(Symbol("p"), Symbol("q")), id="conjunction"),
    pytest.param(lambda: Or(Symbol("p"), Symbol("q")), id="disjunction"),
    pytest.param(lambda: Implies(Symbol("p"), Symbol("q")), id="implication"),
    pytest.param(lambda: Iff(Symbol("p"), Symbol("q")), id="equivalence"),
    pytest.param(lambda: Ite(Symbol("p"), Symbol("q"), Symbol("r")), id="ite"),
    pytest.param(
        lambda: Ite(Symbol("p"), Iff(Symbol("q"), Symbol("r")), Implies(Symbol("s"), Symbol("t"))),
        id="compound-ite",
    ),
    pytest.param(compound_formula, id="compound-conjunction"),
]
ELIMINATION_CASES = [
    pytest.param(lambda: And(Symbol("p"), Or(Symbol("q"), Symbol("r"))), ("q",), id="one-variable"),
    pytest.param(compound_formula, ("q", "t"), id="two-variables"),
]
