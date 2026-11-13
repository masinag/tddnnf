from collections.abc import Collection, Iterable, Sequence
from typing import Any

from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import get_env
from pysmt.typing import BOOL


def owns_dags(env: Environment, formulas: Iterable[FNode]) -> bool:
    """Check that the supplied formulas belong to the selected manager."""
    return all(formula in env.formula_manager for formula in formulas)


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


def compilation_vocabulary(
    formula: FNode, all_atoms: Sequence[FNode], exists_atoms: Sequence[FNode], forall_atoms: Sequence[FNode]
) -> tuple[FNode, ...]:
    """Validate a single quantifier kind and retain declaration order."""
    if exists_atoms and forall_atoms:
        raise ValueError("Cannot combine existential and universal declarations")
    for atoms in (all_atoms, exists_atoms, forall_atoms):
        if any(not isinstance(atom, FNode) or not is_atom(atom) or atom.is_bool_constant() for atom in atoms):
            raise ValueError("Atom declarations must contain Boolean symbols or theory atoms")
        if len(set(atoms)) != len(atoms):
            raise ValueError("Atom declarations must not contain duplicates")
    declared, existential, universal = set(all_atoms), set(exists_atoms), set(forall_atoms)
    if not formula.get_atoms() <= declared:
        raise ValueError("Formula atoms must belong to all_atoms")
    quantified = existential | universal
    if not quantified <= declared or existential & universal:
        raise ValueError("Quantified atoms must be disjoint subsets of all_atoms")
    return tuple(atom for atom in all_atoms if atom not in quantified)
