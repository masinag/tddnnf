"""Native backend save/load preserves semantics across the projected formula bank."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pysmt.formula import FormulaManager

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import PropCompiler
from tests.support import SolverGroundTruth


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
