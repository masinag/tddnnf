from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from pysmt.formula import FormulaManager

from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import PropCompiler
from tests.conftest import SolverGroundTruth


@pytest.fixture(params=[BddCompiler, SddCompiler, D4Compiler])
def compiler(request):
    return request.param()


def test_bank_compilation_equivalence(
    mgr: FormulaManager, compiler: PropCompiler, abstr: Abstractor, bank_case: SolverGroundTruth
) -> None:
    abstr = bank_case.abstr
    target = compiler.compile(bank_case.original_formula, abstr, project_on=bank_case.project_on)
    compiled_pysmt = target.to_pysmt(abstr, mgr)

    not_equivalent = mgr.Not(mgr.Iff(compiled_pysmt, bank_case.expected_formula))
    with mgr.env.factory.Solver() as solver:
        solver.add_assertion(not_equivalent)
        assert not solver.solve(), f"Compilation equivalence failed for {bank_case.original_formula}"


def test_save_load_roundtrip_equivalence(
    mgr: FormulaManager, compiler: PropCompiler, abstr: Abstractor, bank_case: SolverGroundTruth
) -> None:
    abstr = bank_case.abstr
    target = compiler.compile(bank_case.original_formula, abstr, project_on=bank_case.project_on)
    original_pysmt = target.to_pysmt(abstr, mgr)

    with tempfile.TemporaryDirectory() as tmpdir:
        target.save(Path(tmpdir) / "artifact")
        loaded = type(target).load(Path(tmpdir) / "artifact")
        loaded_pysmt = loaded.to_pysmt(abstr, mgr)

        not_equivalent = mgr.Not(mgr.Iff(original_pysmt, loaded_pysmt))
        with mgr.env.factory.Solver() as solver:
            solver.add_assertion(not_equivalent)
            assert not solver.solve(), "Reloaded compiled target differs from original save!"
