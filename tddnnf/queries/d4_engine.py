from __future__ import annotations

import tempfile
from collections.abc import Iterator
from itertools import product
from pathlib import Path

from pysmt.fnode import FNode

from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import QueryEngine
from tddnnf.core.pysmt_utils import clause_lits, cube_lits, normalize_assumptions


class D4Engine(QueryEngine[D4CompiledTarget]):
    """Polynomial-time queries over a d-DNNF compiled target via ddnnife."""

    def __init__(self, container: TheoryCompiledTarget[D4CompiledTarget]) -> None:
        import ddnnife

        self._abstr = container.abstr
        self._care_vars: list[FNode] = list(container.care_vars)
        self._care_set: set[FNode] = set(container.care_vars)
        self._var_count = container.target.var_count
        self._remapping = container.target.remapping

        nnf_text = container.target.nnf_text
        if nnf_text == "t 1\n":
            self._const_true = True
            self._tmpdir = None
            self._mut = None
        elif nnf_text == "f 1\n":
            self._const_true = False
            self._tmpdir = None
            self._mut = None
        else:
            self._const_true = False
            self._tmpdir = tempfile.TemporaryDirectory(prefix="d4_engine_")
            nnf_path = Path(self._tmpdir.name) / "circuit.nnf"
            nnf_path.write_text(nnf_text)
            self._ddnnf = ddnnife.Ddnnf.from_file(str(nnf_path), features=self._var_count)
            self._mut = self._ddnnf.as_mut()

    def __del__(self) -> None:
        if self._tmpdir is not None:
            self._tmpdir.cleanup()

    def _lits_to_ddnnf(self, lits: list[FNode]) -> list[int]:
        result: list[int] = []
        for lit in lits:
            atom = lit.arg(0) if lit.is_not() else lit
            if atom not in self._care_set:
                raise ValueError(f"Atom {atom} is not a care variable")
            var_id = self._abstr.get_id(atom)
            nnf_id = self._remapping[var_id]
            result.append(-nnf_id if lit.is_not() else nnf_id)
        return result

    @property
    def _formula_is_constant(self) -> bool:
        return self._mut is None

    def _gap_shift(self) -> int:
        return max(0, self._var_count - len(self._care_vars))

    def is_satisfiable(self, assumptions: list[FNode] | None = None) -> bool:
        if self._formula_is_constant:
            if not self._const_true:
                return False  # it is the false constant
            # here we know the circuit is the true constant, hence just check
            # contradicition of assumptions
            if not assumptions:
                return True
            return normalize_assumptions(assumptions) is not None
        assert self._mut is not None
        if assumptions is None:
            return self._mut.is_sat([])
        return self._mut.is_sat(self._lits_to_ddnnf(assumptions))

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        if self._formula_is_constant:  # true/false constant
            if assumptions:
                if not self._const_true:
                    return 0
                unique = normalize_assumptions(assumptions)
                if unique is None:
                    return 0
                return 1 << (len(self._care_vars) - len(unique))
            return (1 << len(self._care_vars)) if self._const_true else 0
        if assumptions:
            unique = normalize_assumptions(assumptions)
            if unique is None:
                return 0
            lits = self._lits_to_ddnnf(unique)
        else:
            lits = []
        assert self._mut is not None
        return int(self._mut.count(lits)) >> self._gap_shift()

    def is_valid(self) -> bool:
        return self.count_truth_assignments() == (1 << len(self._care_vars))

    def entails_clause(self, query_clause: FNode) -> bool:
        lits = clause_lits(query_clause)
        if lits is None:
            return True
        negated = [~lit if not lit.is_not() else lit.arg(0) for lit in lits]
        return not self.is_satisfiable(assumptions=negated)

    def is_implicant(self, query_cube: FNode) -> bool:
        lits = cube_lits(query_cube)
        if lits is None:
            return True
        if self._formula_is_constant:
            return self._const_true
        assert self._mut is not None
        ddnnf_lits = self._lits_to_ddnnf(lits)
        count = int(self._mut.count(ddnnf_lits)) >> self._gap_shift()
        remaining = len(self._care_vars) - len(lits)
        return count == (1 << remaining)

    def enumerate_truth_assignments(self) -> Iterator[dict[FNode, bool]]:
        if self._formula_is_constant:
            if self._const_true:
                for bits in product([True, False], repeat=len(self._care_vars)):
                    yield dict(zip(self._care_vars, bits))
            return
        assert self._mut is not None
        total = int(self._mut.count([]))
        if total == 0:
            return
        raw = self._mut.enumerate([], total)
        care_ids = {self._abstr.get_id(a) for a in self._care_vars}
        nnf_to_abstr = {v: k for k, v in self._remapping.items()}
        for model_lits in raw:
            partial: dict[int, bool] = {}
            for lit in model_lits:
                nnf_var_id = abs(lit)
                abstr_id = nnf_to_abstr.get(nnf_var_id)
                if abstr_id is not None and abstr_id in care_ids:
                    partial[abstr_id] = lit > 0
            present = set(partial)
            missing = [a for a in self._care_vars if self._abstr.get_id(a) not in present]
            if not missing:
                yield {a: partial[self._abstr.get_id(a)] for a in self._care_vars}
            else:
                for bits in product([True, False], repeat=len(missing)):
                    full = dict(partial)
                    for atom, val in zip(missing, bits):
                        full[self._abstr.get_id(atom)] = val
                    yield {a: full[self._abstr.get_id(a)] for a in self._care_vars}
