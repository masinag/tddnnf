from collections.abc import Collection
from typing import Any

from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import get_env
from pysmt.typing import BOOL


class SuspendTypeChecking:
    """Context manager that disables pysmt type checking for formula construction."""

    def __init__(self, env: Environment | None = None) -> None:
        self.env = env or get_env()
        self.mgr = self.env.formula_manager
        self._saved: Any = None

    def __enter__(self) -> Environment:
        self._saved = self.mgr._do_type_check
        self.mgr._do_type_check = lambda formula: formula
        return self.env

    def __exit__(self, *_: Any) -> None:
        self.mgr._do_type_check = self._saved


def get_theory_atoms(atoms: Collection[FNode]) -> list[FNode]:
    return [atom for atom in atoms if not atom.is_symbol(BOOL)]


def is_atom(atom: FNode) -> bool:
    return atom.is_symbol(BOOL) or atom.is_theory_relation() or atom.is_bool_constant()


def is_literal(literal: FNode) -> bool:
    return is_atom(literal) or (literal.is_not() and is_atom(literal.arg(0)))


def is_clause(phi: FNode) -> bool:
    return is_literal(phi) or (phi.is_or() and all(is_clause(a) for a in phi.args()))


def is_cube(phi: FNode) -> bool:
    return is_literal(phi) or (phi.is_and() and all(is_cube(a) for a in phi.args()))


def _query_lits(
    literals: list[FNode], projection_atoms: Collection[FNode], *, disjunction: bool = False
) -> list[FNode] | None:
    """Validate all flat literals before simplifying their Boolean semantics."""
    for lit in literals:
        if not isinstance(lit, FNode) or not is_literal(lit):
            raise ValueError("Expected a flat list of Boolean literals")
        atom = lit.arg(0) if lit.is_not() else lit
        if not atom.is_bool_constant() and atom not in projection_atoms:
            raise ValueError(f"Atom {atom} is not a projection atom")

    polarity: dict[FNode, bool] = {}
    unique: list[FNode] = []
    for lit in literals:
        atom = lit.arg(0) if lit.is_not() else lit
        is_neg = lit.is_not()
        if atom.is_bool_constant():
            if (atom.is_true() ^ is_neg) == disjunction:
                return None
            continue
        if atom in polarity:
            if polarity[atom] != is_neg:
                return None
        else:
            polarity[atom] = is_neg
            unique.append(lit)
    return unique


def clause_lits(clause: list[FNode], projection_atoms: Collection[FNode]) -> list[FNode] | None:
    """Return deduplicated, nonconstant clause literals, or None if tautological."""
    return _query_lits(clause, projection_atoms, disjunction=True)


def cube_lits(cube: list[FNode], projection_atoms: Collection[FNode]) -> list[FNode] | None:
    """Return deduplicated, nonconstant cube literals, or None if contradictory."""
    return _query_lits(cube, projection_atoms)
