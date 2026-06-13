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


def clause_lits(clause: FNode) -> list[FNode] | None:
    stack = [clause]
    res: list[FNode] = []
    polarity: dict[FNode, bool] = {}
    while stack:
        lit = stack.pop()
        if lit.is_true():
            return None
        elif lit.is_false():
            continue
        elif is_literal(lit):
            atom = lit.arg(0) if lit.is_not() else lit
            is_neg = lit.is_not()
            if atom in polarity:
                if polarity[atom] != is_neg:
                    return None
            else:
                polarity[atom] = is_neg
                res.append(lit)
        elif lit.is_or():
            stack += lit.args()
        else:
            raise ValueError(f"Expected a clause, got: {clause}")
    return res


def cube_lits(cube: FNode) -> list[FNode] | None:
    stack = [cube]
    res: list[FNode] = []
    polarity: dict[FNode, bool] = {}
    while stack:
        lit = stack.pop()
        if lit.is_true():
            continue
        elif lit.is_false():
            return None
        elif is_literal(lit):
            atom = lit.arg(0) if lit.is_not() else lit
            is_neg = lit.is_not()
            if atom in polarity:
                if polarity[atom] != is_neg:
                    return None
            else:
                polarity[atom] = is_neg
                res.append(lit)
        elif lit.is_and():
            stack += lit.args()
        else:
            raise ValueError(f"Expected a cube, got: {cube}")
    return res
