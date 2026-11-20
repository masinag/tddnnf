from collections.abc import Collection, Iterable, Sequence
from typing import Any

from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import get_env
from pysmt.typing import BOOL


def owns_dags(env: Environment, terms: Iterable[FNode]) -> bool:
    """Check that the supplied terms belong to the given environment.

    Args:
        env: the PySMT environment.
        terms: a list of PySMT terms.

    Returns:
        bool: whether all terms belong to the given environment.
    """
    return all(formula in env.formula_manager for formula in terms)


class SuspendTypeChecking:
    """Context manager that disables PySMT type checking for formula construction (for efficiency reasons)."""

    def __init__(self, env: Environment | None = None) -> None:
        self.env = env or get_env()
        self.mgr = self.env.formula_manager
        self._saved: Any = None

    def __enter__(self) -> Environment:
        self._saved = self.mgr._do_type_check
        self.mgr._do_type_check = lambda formula: None
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


def _query_literals(
    literals: list[FNode], projection_atoms: Collection[FNode], *, disjunction: bool = False
) -> list[FNode] | None:
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
            # a
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


def clause_literals(clause: list[FNode], projection_atoms: Collection[FNode]) -> list[FNode] | None:
    """Check and simplify the given list of literals, interpreted as a clause.

    Args:
        clause: The clause literals.
        projection_atoms: The atoms that can appear in the clause.

    Returns:
        list[FNode] | None: The simplified clause obtained by removing redundant literals,
            or None if it's propositionally tautological.

    Raises:
        ValueError: If the clause is not formed by literals over the supplied projection atoms.
    """
    return _query_literals(clause, projection_atoms, disjunction=True)


def cube_literals(cube: list[FNode], projection_atoms: Collection[FNode]) -> list[FNode] | None:
    """Check and simplify the given list of literals, interpreted as a cube.

    Args:
        cube: The cube literals.
        projection_atoms: The atoms that can appear in the cube.

    Returns:
        list[FNode] | None: The simplified cube obtained by removing redundant literals,
            or None if it's propositionally contradictory.

    Raises:
        ValueError: If the cube is not formed by literals over the supplied projection atoms.
    """
    return _query_literals(cube, projection_atoms)


def compilation_vocabulary(
    formula: FNode, all_atoms: Sequence[FNode], exists_atoms: Sequence[FNode], forall_atoms: Sequence[FNode]
) -> tuple[FNode, ...]:
    """Validate atom declarations and return the unquantified compilation vocabulary.

    Args:
        formula: Formula whose atoms must be declared in all_atoms.
        all_atoms: All declared atoms, including quantified ones.
        exists_atoms: Atoms declared as existentially quantified.
        forall_atoms: Atoms declared as universally quantified.

    Returns:
        Tuple of unquantified atoms, preserving their order in all_atoms.

    Raises:
        ValueError: If declarations contain invalid or duplicate atoms, if formula
            atoms are undeclared, or if quantified atoms are not subsets of
            all_atoms or both quantifier types are used.
    """
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
