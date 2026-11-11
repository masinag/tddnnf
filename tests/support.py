"""Shared solver oracles, backend pairings, and target construction helpers."""

from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.queries import BddEngine, DdnnifeEngine, SddEngine

PAIRINGS = [(BddCompiler, BddEngine), (SddCompiler, SddEngine), (D4Compiler, DdnnifeEngine)]
BACKENDS = [compiler for compiler, _ in PAIRINGS]
STRATEGIES = ["compile_treduced", "compile_textended"]


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
        self.abstr = Abstractor(dict(enumerate(all_vars, 1)))
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


def equivalent(mgr, actual, expected):
    with mgr.env.factory.Solver() as solver:
        solver.add_assertion(mgr.Not(mgr.Iff(actual, expected)))
        assert not solver.solve()


def compile_target(mgr, pairing, formula, atoms):
    with TheoryCompilation(formula, project_on=atoms, env=mgr.env) as compilation:
        return compilation.compile_treduced(pairing[0](), [])
