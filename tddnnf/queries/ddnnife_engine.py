from __future__ import annotations

import tempfile
from pathlib import Path

import ddnnife

from tddnnf.compilation.d4 import D4CompiledTarget
from tddnnf.compilation.targets import TheoryCompiledTarget
from tddnnf.queries.ddnnf_engine import GenericDdnnfEngine


class DdnnifeEngine(GenericDdnnfEngine):
    """Reason over a D4-compiled d-DNNF, using the ddnnife query engine."""

    def __init__(self, theory_target: TheoryCompiledTarget[D4CompiledTarget]) -> None:
        super().__init__(theory_target)
        self._tmpdir = None
        if not isinstance(theory_target.target, D4CompiledTarget):
            raise TypeError("DdnnifeEngine requires D4CompiledTarget")

        self._mut = None
        self._ddnnf = None
        self._tmpdir = tempfile.TemporaryDirectory(prefix="ddnnife_engine_")
        try:
            nnf_path = Path(self._tmpdir.name) / "circuit.nnf"
            nnf_path.write_text(theory_target.target.nnf_text)
            # ddnnife errors for unsupported constant circuits intentionally propagate.
            self._ddnnf = ddnnife.Ddnnf.from_file(str(nnf_path), features=self._var_count)
            self._mut = self._ddnnf.as_mut()
        except BaseException:
            self.close()
            raise

    def __del__(self) -> None:
        self.close()

    def close(self) -> None:
        """Release the native circuit and temporary file, including on load failure."""
        self._mut = None
        self._ddnnf = None
        tmpdir, self._tmpdir = getattr(self, "_tmpdir", None), None
        if tmpdir is not None:
            tmpdir.cleanup()

    def _is_satisfiable(self, assumptions: list[int]) -> bool:
        assert self._mut is not None
        return self._mut.is_sat(assumptions)

    def _count_truth_assignments(self, assumptions: list[int]) -> int:
        assert self._mut is not None
        return int(self._mut.count(assumptions))

    def _enumerate_truth_assignments(self) -> list[list[int]]:
        assert self._mut is not None
        total = int(self._mut.count([]))
        return self._mut.enumerate([], total)
