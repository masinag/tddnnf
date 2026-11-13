from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING

from pysmt.fnode import FNode

from tddnnf.compilers.cudd import BddCompiledTarget

if TYPE_CHECKING:
    from tddnnf.core.theory_compiled_target import TheoryCompiledTarget
from tddnnf.core.interfaces import QueryEngine
from tddnnf.core.pysmt_utils import clause_lits, cube_lits


class BddEngine(QueryEngine[BddCompiledTarget]):
    """Polynomial-time queries over a BDD compiled target."""

    def __init__(self, container: TheoryCompiledTarget[BddCompiledTarget]) -> None:
        if not isinstance(container.target, BddCompiledTarget):
            raise TypeError("BddEngine requires BddCompiledTarget")
        self._target = container.target
        self._abstr = container.abstr
        self._atoms: tuple[FNode, ...] = container.atoms
        self._atom_set: set[FNode] = set(container.atoms)

    def _restrict_chain(self, lits: list[FNode], negate: bool = False, root=None):
        """Restrict by validated literals, flipping each sign when negate is True.

        Callers must first use clause_lits or cube_lits with the exact target
        atoms and handle None. Inputs must be constant-free, deduplicated literals
        over those atoms, with no complementary pair.
        """
        assign: dict[str, bool] = {}
        for lit in lits:
            atom = lit.arg(0) if lit.is_not() else lit
            val = (not lit.is_not()) if not negate else lit.is_not()
            name = f"b{self._abstr.get_id(atom)}"
            assign[name] = val
        source = self._target.root if root is None else root
        if not assign:
            return source
        mgr = self._target.manager
        return mgr.let(assign, source)

    def is_satisfiable(self, assumptions: list[FNode] | None = None) -> bool:
        unique = cube_lits(assumptions or [], self._atom_set)
        if unique is None:
            return False
        mgr = self._target.manager
        return self._restrict_chain(unique, negate=False) != mgr.false

    def _forgotten_var_count(self) -> int:
        return len(self._target.manager.vars) - len(self._atoms)

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        unique = cube_lits(assumptions or [], self._atom_set)
        if unique is None:
            return 0
        n = len(self._target.manager.vars)
        forgotten = self._forgotten_var_count()
        restricted = self._restrict_chain(unique, negate=False)
        total = restricted.count(n)
        return int(total) >> (forgotten + len(unique))

    def is_valid(self) -> bool:
        return self._target.root == self._target.manager.true

    def entails_clause(self, query_clause: list[FNode]) -> bool:
        lits = clause_lits(query_clause, self._atom_set)
        if lits is None:
            return True
        mgr = self._target.manager
        return self._restrict_chain(lits, negate=True) == mgr.false

    def is_implicant(self, query_cube: list[FNode]) -> bool:
        lits = cube_lits(query_cube, self._atom_set)
        if lits is None:
            return True
        mgr = self._target.manager
        return self._restrict_chain(lits) == mgr.true

    def enumerate_truth_assignments(self) -> Generator[dict[FNode, bool], None, None]:
        root = self._target.root
        if root == self._target.manager.false:
            return
        mgr = self._target.manager
        atom_ids = {f"b{self._abstr.get_id(atom)}": atom for atom in self._atoms}
        for assignment in mgr.pick_iter(root, care_vars=set(atom_ids)):
            yield {atom: assignment[name] for name, atom in atom_ids.items()}
