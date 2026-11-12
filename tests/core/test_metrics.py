"""Exact native DAG metrics, including BDD edges reached along shared paths."""

import pytest
from pysmt.formula import FormulaManager

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.interfaces import DagSize


def _bool_symbols(mgr, count):
    return [mgr.Symbol(f"v{i}") for i in range(count)]


@pytest.mark.parametrize(
    "text,var_count,expected",
    [
        ("a 1\nt 2\n1 2 1 0\n", 1, DagSize(vertices=3, edges=2)),
        ("a 1\nt 2\nt 3\nt 4\n1 2 1 0\n1 3 2 0\n1 4 3 0\n", 3, DagSize(vertices=7, edges=6)),
    ],
    ids=["small", "larger"],
)
def test_d4_target_dag_size(text, var_count, expected):
    assert D4CompiledTarget(text, var_count).dag_size() == expected


@pytest.mark.parametrize(
    "larger,expected",
    [(False, DagSize(vertices=2, edges=4)), (True, DagSize(vertices=15, edges=30))],
    ids=["small", "larger"],
)
def test_sdd_target_dag_size(mgr, larger, expected):
    a, b, c, d, e, f = _bool_symbols(mgr, 6)
    formula = mgr.And(mgr.Or(a, b), mgr.Or(c, d), mgr.Or(e, f)) if larger else mgr.And(a, b)
    with TheoryCompilation(formula, env=mgr.env) as compilation:
        target = compilation.compile_treduced(SddCompiler(), []).target
    assert target.dag_size() == expected


@pytest.mark.parametrize(
    "larger,expected",
    [(False, DagSize(vertices=3, edges=4)), (True, DagSize(vertices=7, edges=12))],
    ids=["small", "larger"],
)
def test_bdd_target_dag_size(mgr, larger, expected):
    a, b, c, d, e, f = _bool_symbols(mgr, 6)
    formula = mgr.And(mgr.Or(a, b), mgr.Or(c, d), mgr.Or(e, f)) if larger else mgr.And(a, b)
    with TheoryCompilation(formula, env=mgr.env) as compilation:
        target = compilation.compile_treduced(BddCompiler(), []).target
    assert target.dag_size() == expected


def test_larger_bdd_target_dag_size_with_shared_paths(mgr: FormulaManager) -> None:
    a, b, c, d = _bool_symbols(mgr, 4)
    formula = mgr.Xor(mgr.Xor(a, b), mgr.Xor(c, d))
    target = TheoryCompilation(formula, env=mgr.env).compile_treduced(BddCompiler(), []).target

    assert target.dag_size() == DagSize(vertices=5, edges=14)
