from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

import ddnnife
from pysmt.fnode import FNode

from tddnnf.compilers.d4 import D4CompiledTarget

if TYPE_CHECKING:
    from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import QueryEngine
from tddnnf.core.pysmt_utils import clause_lits, cube_lits, normalize_assumptions


class DdnnifeEngine(QueryEngine[D4CompiledTarget]):
    """Polynomial-time queries over a d-DNNF compiled target via ddnnife."""

    def __init__(self, container: TheoryCompiledTarget[D4CompiledTarget]) -> None:

        self._tmpdir = None
        if not isinstance(container.target, D4CompiledTarget):
            raise TypeError("DdnnifeEngine requires D4CompiledTarget")
        self._abstr = container.abstr
        self._projection_atoms: tuple[FNode, ...] = container.projection_atoms
        self._projection_atom_set: set[FNode] = set(container.projection_atoms)
        self._var_count = container.target.var_count
        self._remapping = container.target.remapping

        self._tmpdir = None
        self._mut = None
        self._ddnnf = None
        nnf_text = container.target.nnf_text
        if nnf_text not in ("t 1\n", "f 1\n"):
            # Every projected dimension is mapped, even when absent from the DAG.
            ids = {self._abstr.get_id(a) for a in self._projection_atoms}
            assert set(self._remapping) == ids, "D4 mapping must cover exactly the projection"
            assert len(self._remapping) == self._var_count == len(self._projection_atoms)
            assert set(self._remapping.values()) == set(range(1, self._var_count + 1))
        self._tmpdir = tempfile.TemporaryDirectory(prefix="ddnnife_engine_")
        try:
            nnf_path = Path(self._tmpdir.name) / "circuit.nnf"
            nnf_path.write_text(nnf_text)
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

    def _lits_to_ddnnf(self, lits: list[FNode]) -> list[int]:
        result: list[int] = []
        for lit in lits:
            atom = lit.arg(0) if lit.is_not() else lit
            if atom not in self._projection_atom_set:
                raise ValueError(f"Atom {atom} is not a projection atom")
            var_id = self._abstr.get_id(atom)
            nnf_id = self._remapping[var_id]
            result.append(-nnf_id if lit.is_not() else nnf_id)
        return result

    def is_satisfiable(self, assumptions: list[FNode] | None = None) -> bool:
        unique = normalize_assumptions(assumptions or [])
        if unique is None:
            return False
        assert self._mut is not None
        return self._mut.is_sat(self._lits_to_ddnnf(unique))

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        unique = normalize_assumptions(assumptions or [])
        if unique is None:
            return 0
        assert self._mut is not None
        return int(self._mut.count(self._lits_to_ddnnf(unique)))

    def is_valid(self) -> bool:
        return self.count_truth_assignments() == (1 << len(self._projection_atoms))

    def entails_clause(self, query_clause: FNode) -> bool:
        lits = clause_lits(query_clause)
        if lits is None:
            return True
        # Negate backend literals to avoid depending on PySMT's active environment.
        negated = [-lit for lit in self._lits_to_ddnnf(lits)]
        assert self._mut is not None
        return not self._mut.is_sat(negated)

    def is_implicant(self, query_cube: FNode) -> bool:
        lits = cube_lits(query_cube)
        if lits is None:
            return True
        assert self._mut is not None
        ddnnf_lits = self._lits_to_ddnnf(lits)
        count = int(self._mut.count(ddnnf_lits))
        remaining = len(self._projection_atoms) - len(lits)
        return count == (1 << remaining)

    def enumerate_truth_assignments(self) -> Generator[dict[FNode, bool], None, None]:
        assert self._mut is not None
        total = int(self._mut.count([]))
        raw = self._mut.enumerate([], total)
        for model_lits in raw:
            assignment = {abs(lit): lit > 0 for lit in model_lits}
            yield {a: assignment[self._remapping[self._abstr.get_id(a)]] for a in self._projection_atoms}
