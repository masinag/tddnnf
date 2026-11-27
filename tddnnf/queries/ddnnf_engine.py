from typing import Generator

from pysmt.fnode import FNode

from tddnnf.compilation.d4 import D4CompiledTarget
from tddnnf.compilation.targets import TheoryCompiledTarget
from tddnnf.core.pysmt_utils import clause_literals, cube_literals
from tddnnf.queries.engine import QueryEngine


class GenericDdnnfEngine(QueryEngine[D4CompiledTarget]):
    """
    Generic d-DNNF query engine that implements standard query reductions, requiring the implementation of basic
    queries only.
    """

    def __init__(self, theory_target: TheoryCompiledTarget[D4CompiledTarget]) -> None:
        if not isinstance(theory_target.target, D4CompiledTarget):
            raise TypeError(
                f"theory_target.target must be an instance of D4CompiledTarget, {type(theory_target.target)} found"
            )
        self._abstr = theory_target.abstr
        self._atoms: tuple[FNode, ...] = theory_target.atoms
        self._atom_set: set[FNode] = set(theory_target.atoms)
        self._var_count = theory_target.target.var_count
        self._remapping = theory_target.target.remapping
        nnf_text = theory_target.target.nnf_text
        if nnf_text not in ("t 1\n", "f 1\n"):
            # Every target atom is mapped, even when absent from the DAG.
            ids = {self._abstr.get_id(a) for a in self._atoms}
            assert ids <= self._remapping.keys(), "D4 mapping must cover the target atoms"

    def _get_lits(self, lits: list[FNode], negate: bool = False) -> list[int]:
        """Convert the given list of literals to a list of signed IDs to condition the d-DNNF on, flipping each sign
         when negate is True.

        The lits list cannot contain duplicates, constants, or contradictory literals.
        """
        result: list[int] = []
        for lit in lits:
            atom = lit.arg(0) if lit.is_not() else lit
            var_id = self._abstr.get_id(atom)
            nnf_id = self._remapping[var_id]
            result.append(-nnf_id if lit.is_not() ^ negate else nnf_id)
        return result

    def _is_satisfiable(self, assumptions: list[int]) -> bool:
        raise NotImplementedError()

    def is_satisfiable(self, assumptions: list[FNode] | None = None) -> bool:
        unique = cube_literals(assumptions or [], self._atom_set)
        if unique is None:
            return False
        return self._is_satisfiable(self._get_lits(unique))

    def _count_truth_assignments(self, assumptions: list[int]) -> int:
        raise NotImplementedError()

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        unique = cube_literals(assumptions or [], self._atom_set)
        if unique is None:
            return 0
        return self._count_truth_assignments(self._get_lits(unique))

    def is_valid(self) -> bool:
        return self.count_truth_assignments() == (1 << len(self._atoms))

    def entails_clause(self, query_clause: list[FNode]) -> bool:
        lits = clause_literals(query_clause, self._atom_set)
        if lits is None:
            return True
        return not self._is_satisfiable(self._get_lits(lits, negate=True))

    def is_implicant(self, query_cube: list[FNode]) -> bool:
        lits = cube_literals(query_cube, self._atom_set)
        if lits is None:
            return True
        count = self._count_truth_assignments(self._get_lits(lits))
        remaining = len(self._atoms) - len(lits)
        return count == (1 << remaining)

    def _enumerate_truth_assignments(self) -> list[list[int]]:
        raise NotImplementedError()

    def enumerate_truth_assignments(self) -> Generator[dict[FNode, bool], None, None]:
        raw = self._enumerate_truth_assignments()
        for model_lits in raw:
            assignment = {abs(lit): lit > 0 for lit in model_lits}
            yield {a: assignment[self._remapping[self._abstr.get_id(a)]] for a in self._atoms}
