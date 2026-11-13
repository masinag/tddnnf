"""All backends reconstruct the projected formula bank equivalently to the solver."""

from __future__ import annotations

from pysmt.formula import FormulaManager

from tddnnf.core.interfaces import PropCompiler
from tests.support import SolverGroundTruth


def test_bank_compilation_equivalence(
    mgr: FormulaManager, compiler: PropCompiler, bank_case: SolverGroundTruth
) -> None:
    abstr = bank_case.abstr
    target = compiler.compile(
        bank_case.original_formula, abstr, all_atoms=bank_case.all_atoms, exists_atoms=bank_case.vars_to_forget
    )
    compiled_pysmt = target.to_pysmt(abstr, mgr)

    not_equivalent = mgr.Not(mgr.Iff(compiled_pysmt, bank_case.expected_formula))
    with mgr.env.factory.Solver() as solver:
        solver.add_assertion(not_equivalent)
        assert not solver.solve(), f"Compilation equivalence failed for {bank_case.original_formula}"
