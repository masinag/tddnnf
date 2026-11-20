from __future__ import annotations

from collections.abc import Generator

from dd.cudd import Function
from pysmt.fnode import FNode

from tddnnf.compilation.cudd import CuddCompiledTarget
from tddnnf.compilation.targets import TheoryCompiledTarget
from tddnnf.core.pysmt_utils import clause_literals, cube_literals
from tddnnf.queries.engine import QueryEngine


class CuddEngine(QueryEngine[CuddCompiledTarget]):
    """Reason over a Cudd-compiled OBDD, using the Cudd manipulation and querying functionalities."""

    def __init__(self, target: TheoryCompiledTarget[CuddCompiledTarget]) -> None:
        if not isinstance(target.target, CuddCompiledTarget):
            raise TypeError("CuddEngine requires CuddCompiledTarget")
        self._target = target.target
        self._abstr = target.abstr
        self._atoms: tuple[FNode, ...] = target.atoms
        self._atom_set: set[FNode] = set(target.atoms)

    def _restrict_chain(self, lits: list[FNode], negate: bool = False, root=None) -> Function:
        """Condition the OBDD on the given literals, flipping each sign when negate is True.

        The lits list cannot contain duplicates, constants, or contradictory literals.
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
        unique = cube_literals(assumptions or [], self._atom_set)
        if unique is None:
            return False
        mgr = self._target.manager
        return self._restrict_chain(unique, negate=False) != mgr.false

    def _forgotten_var_count(self) -> int:
        return len(self._target.manager.vars) - len(self._atoms)

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        unique = cube_literals(assumptions or [], self._atom_set)
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
        lits = clause_literals(query_clause, self._atom_set)
        if lits is None:
            return True
        mgr = self._target.manager
        return self._restrict_chain(lits, negate=True) == mgr.false

    def is_implicant(self, query_cube: list[FNode]) -> bool:
        lits = cube_literals(query_cube, self._atom_set)
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
