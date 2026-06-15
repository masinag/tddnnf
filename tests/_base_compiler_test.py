from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from pysmt.formula import FormulaManager

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import PropCompiledTarget, PropCompiler
from tests.conftest import SolverGroundTruth


class BaseTestCompiler:
    compiler_cls: type[PropCompiler]
    target_cls: type[PropCompiledTarget]

    @pytest.fixture
    def compiler(self, abstr: Abstractor) -> PropCompiler:
        return self.compiler_cls(abstr)

    def test_bank_compilation_equivalence(
        self, mgr: FormulaManager, compiler: PropCompiler, abstr: Abstractor, bank_case: SolverGroundTruth
    ) -> None:
        target = compiler.compile(bank_case.original_formula, project_on=bank_case.project_on)
        compiled_pysmt = target.to_pysmt(abstr, mgr)

        not_equivalent = mgr.Not(mgr.Iff(compiled_pysmt, bank_case.expected_formula))
        with mgr.env.factory.Solver() as solver:
            solver.add_assertion(not_equivalent)
            assert not solver.solve(), f"Compilation equivalence failed for {bank_case.original_formula}"

    def test_save_load_roundtrip_equivalence(
        self, mgr: FormulaManager, compiler: PropCompiler, abstr: Abstractor, bank_case: SolverGroundTruth
    ) -> None:
        target = compiler.compile(bank_case.original_formula, project_on=bank_case.project_on)
        original_pysmt = target.to_pysmt(abstr, mgr)

        with tempfile.TemporaryDirectory() as tmpdir:
            target.save(Path(tmpdir))
            loaded = self.target_cls.load(Path(tmpdir))
            loaded_pysmt = loaded.to_pysmt(abstr, mgr)

            not_equivalent = mgr.Not(mgr.Iff(original_pysmt, loaded_pysmt))
            with mgr.env.factory.Solver() as solver:
                solver.add_assertion(not_equivalent)
                assert not solver.solve(), "Reloaded compiled target differs from original save!"
