from __future__ import annotations

from collections.abc import Mapping
from io import StringIO
from types import MappingProxyType

from pysmt.environment import Environment, get_env
from pysmt.fnode import FNode
from pysmt.smtlib.parser import SmtLibParser
from pysmt.smtlib.script import smtlibscript_from_formula

from tddnnf.core.pysmt_utils import is_atom


class Abstractor:
    """Bidirectional map between atoms and integer IDs.

    If a dictionary is given, then known atoms are mapped according to the given mapping.
    Unknown atoms are assigned new IDs.
    """

    def __init__(self, abstraction: Mapping[int, FNode] | None = None) -> None:
        """Initialize the abstractor with the given mapping.

        Args:
            abstraction: Mapping from integer IDs to atoms.

        Raises:
            ValueError: If the abstraction contains Boolean constants (true or false).
        """
        atoms = dict(abstraction) if abstraction is not None else {}
        if any(atom.is_bool_constant() for atom in atoms.values()):
            raise ValueError("Boolean constants cannot be abstracted")
        self._id_to_atom = atoms
        self._atom_to_id = {atom: idx for idx, atom in atoms.items()}

    @property
    def id_to_atom(self) -> Mapping[int, FNode]:
        return MappingProxyType(self._id_to_atom)

    @property
    def atom_to_id(self) -> Mapping[FNode, int]:
        return MappingProxyType(self._atom_to_id)

    @property
    def var_count(self) -> int:
        return len(self._atom_to_id)

    @property
    def max_var(self) -> int:
        return max(self._id_to_atom) if self._id_to_atom else 0

    def __contains__(self, smt_atom: FNode) -> bool:
        return smt_atom in self._atom_to_id

    def get_id(self, smt_atom: FNode) -> int:
        """Return the integer ID assigned to smt_atom.

        If the atom is not known, it is assigned a new ID and registered in the mapping.

        Args:
            smt_atom: The smt_atom.

        Returns:
            int: The integer ID assigned to smt_atom.

        Raises:
            ValueError: If the atom is a Boolean constant (true or false).
        """
        if smt_atom.is_bool_constant():
            raise ValueError("Boolean constants cannot be abstracted")
        assert is_atom(smt_atom), f"expected atom, got {smt_atom}"
        if smt_atom not in self._atom_to_id:
            idx = self.max_var + 1
            self._atom_to_id[smt_atom] = idx
            self._id_to_atom[idx] = smt_atom
        return self._atom_to_id[smt_atom]

    def get_atom(self, idx: int) -> FNode:
        """Return the atom with the given ID.

        Args:
            idx: The atom ID.

        Returns:
            FNode: The atom with the given ID.

        Raises:
            ValueError: If the ID is not positive.
            KeyError: If the positive ID is not in the mapping.
        """
        if idx <= 0:
            raise ValueError(f"expected positive idx, got {idx}")
        return self._id_to_atom[idx]

    def to_dict(self) -> dict[str, int]:
        """Return a serializable representation of the abstractor."""
        result: dict[str, int] = {}
        for atom, idx in self._atom_to_id.items():
            script = smtlibscript_from_formula(atom)
            buf = StringIO()
            script.serialize(buf, daggify=False)
            result[buf.getvalue()] = idx
        return result

    @classmethod
    def from_dict(cls, data: dict[str, int], env: Environment | None = None) -> Abstractor:
        """Deserialize the abstractor from a dictionary."""
        env = env or get_env()
        mgr = env.formula_manager
        id_to_atom: dict[int, FNode] = {}
        parser = SmtLibParser(env)
        for smtlib_str, idx in data.items():
            script = parser.get_script(StringIO(smtlib_str))
            atom = script.get_last_formula(mgr)
            assert atom is not None
            id_to_atom[idx] = atom
        return cls(id_to_atom)
