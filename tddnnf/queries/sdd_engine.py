from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING

from pysmt.fnode import FNode

from tddnnf.compilers.pysdd import SddCompiledTarget

if TYPE_CHECKING:
    from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import QueryEngine
from tddnnf.core.pysmt_utils import clause_lits, cube_lits


class SddEngine(QueryEngine[SddCompiledTarget]):
    """Polynomial-time queries over an SDD compiled target."""

    def __init__(self, container: TheoryCompiledTarget[SddCompiledTarget]) -> None:
        if not isinstance(container.target, SddCompiledTarget):
            raise TypeError("SddEngine requires SddCompiledTarget")
        self._target = container.target
        self._abstr = container.abstr
        self._projection_atoms: tuple[FNode, ...] = container.projection_atoms
        self._projection_atom_set: set[FNode] = set(container.projection_atoms)

    def _condition_chain(self, lits: list[FNode], negate: bool = False, root=None):
        """Condition on validated literals, flipping each sign when negate is True.

        Callers must first use clause_lits or cube_lits with the exact projection
        atoms and handle None. Inputs must be constant-free, deduplicated literals
        over those atoms, with no complementary pair.
        """
        temp = self._target.root if root is None else root
        for lit in lits:
            atom = lit.arg(0) if lit.is_not() else lit
            var_id = self._target.remapping[self._abstr.get_id(atom)]
            sdd_lit = self._target.manager.literal(-var_id if lit.is_not() ^ negate else var_id)
            temp = temp.condition(sdd_lit)
            if temp.is_false():
                break
        return temp

    def is_satisfiable(self, assumptions: list[FNode] | None = None) -> bool:
        unique = cube_lits(assumptions or [], self._projection_atom_set)
        if unique is None:
            return False
        return not bool(self._condition_chain(unique, negate=False).is_false())

    def _forgotten_var_count(self) -> int:
        return self._target.manager.var_count() - len(self._projection_atoms)

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        unique = cube_lits(assumptions or [], self._projection_atom_set)
        if unique is None:
            return 0
        temp = self._condition_chain(unique, negate=False)
        return temp.global_model_count() >> (self._forgotten_var_count() + len(unique))

    def is_valid(self) -> bool:
        return bool(self._target.root.is_true())

    def entails_clause(self, query_clause: list[FNode]) -> bool:
        lits = clause_lits(query_clause, self._projection_atom_set)
        if lits is None:
            return True
        return bool(self._condition_chain(lits, negate=True).is_false())

    def is_implicant(self, query_cube: list[FNode]) -> bool:
        lits = cube_lits(query_cube, self._projection_atom_set)
        if lits is None:
            return True
        return bool(self._condition_chain(lits).is_true())

    def enumerate_truth_assignments(self) -> Generator[dict[FNode, bool], None, None]:
        root = self._target.root
        if root.is_false():
            return
        mgr = self._target.manager
        projection_ids = {self._target.remapping[self._abstr.get_id(a)]: a for a in self._projection_atoms}
        # Forgotten variables are unconstrained; fix them to false to avoid duplicate projected models.
        for var_id in range(1, mgr.var_count() + 1):
            if var_id not in projection_ids:
                root = root & mgr.literal(-var_id)
        for assignment in root.models(vtree=mgr.vtree()):
            yield {atom: assignment[var_id] == 1 for var_id, atom in projection_ids.items()}
