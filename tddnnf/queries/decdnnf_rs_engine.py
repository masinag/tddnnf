from __future__ import annotations

import tempfile
from pathlib import Path

import decdnnf_rs_py

from tddnnf.compilation.d4 import D4CompiledTarget
from tddnnf.compilation.targets import TheoryCompiledTarget
from tddnnf.queries.ddnnf_engine import GenericDdnnfEngine


class DecDnnfRsEngine(GenericDdnnfEngine):
    """Reason over a D4-compiled d-DNNF, using the decdnnf_rs query engine."""

    def __init__(self, theory_target: TheoryCompiledTarget[D4CompiledTarget]) -> None:
        super().__init__(theory_target)
        self._tmpdir = None
        if not isinstance(theory_target.target, D4CompiledTarget):
            raise TypeError("DdnnifeEngine requires D4CompiledTarget")

        self._ddnnf = None
        nnf_text = theory_target.target.nnf_text
        self._tmpdir = tempfile.TemporaryDirectory(prefix="ddnnife_engine_")
        try:
            nnf_path = Path(self._tmpdir.name) / "circuit.nnf"
            nnf_path.write_text(nnf_text)
            # ddnnife errors for unsupported constant circuits intentionally propagate.
            self._ddnnf = decdnnf_rs_py.PyDecisionDNNF(str(nnf_path))
            self._ddnnf.update_n_vars(self._var_count)  # pyright: ignore[reportAttributeAccessIssue]
        except BaseException as ex:
            self.close()
            raise ValueError(f"Bad input {nnf_text}") from ex

    def __del__(self) -> None:
        self.close()

    def close(self) -> None:
        """Release the native circuit and temporary file, including on load failure."""
        self._ddnnf = None
        tmpdir, self._tmpdir = getattr(self, "_tmpdir", None), None
        if tmpdir is not None:
            tmpdir.cleanup()

    def _is_satisfiable(self, assumptions: list[int]) -> bool:
        assert self._ddnnf is not None
        return self._ddnnf.model(assumptions=assumptions) is not None  # pyright: ignore[reportAttributeAccessIssue]

    def _count_truth_assignments(self, assumptions: list[int]) -> int:
        assert self._ddnnf is not None
        return self._ddnnf.count_models(assumptions=assumptions)  # pyright: ignore[reportAttributeAccessIssue]

    def _enumerate_truth_assignments(self) -> list[list[int]]:
        assert self._ddnnf is not None
        models = []
        # enumerate total truth assignments
        self._ddnnf.enumerate_models(lambda m: models.append(m), compact=False)  # pyright: ignore[reportAttributeAccessIssue]
        return models
