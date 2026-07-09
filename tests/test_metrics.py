from __future__ import annotations

from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import DagSize


def test_d4_target_dag_size() -> None:
    nnf_text = "a 1\nt 2\n1 2 1 0\n"
    target = D4CompiledTarget(nnf_text=nnf_text, var_count=1)

    assert target.dag_size() == DagSize(vertices=3, edges=2)


def test_sdd_target_dag_size(mgr: FormulaManager, a: FNode, b: FNode) -> None:
    target = SddCompiler(Abstractor()).compile(mgr.And(a, b))

    assert target.dag_size() == DagSize(vertices=2, edges=4)


def test_bdd_target_dag_size(mgr: FormulaManager, a: FNode, b: FNode) -> None:
    target = BddCompiler(Abstractor()).compile(mgr.And(a, b))

    assert target.dag_size() == DagSize(vertices=3, edges=4)
