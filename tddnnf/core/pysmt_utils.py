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
