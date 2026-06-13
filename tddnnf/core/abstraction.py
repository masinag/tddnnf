from __future__ import annotations

from io import StringIO

from pysmt.environment import Environment, get_env
from pysmt.fnode import FNode
from pysmt.smtlib.parser import SmtLibParser
from pysmt.smtlib.script import smtlibscript_from_formula

from tddnnf.core.pysmt_utils import is_atom


class Abstractor:
    """Bidirectional map between SMT atoms (Bool or theory) and integer IDs."""

    def __init__(self, abstraction: dict[int, FNode] | None = None) -> None:
        self._id_to_atom: dict[int, FNode] = abstraction if abstraction is not None else {}
        self._atom_to_id: dict[FNode, int] = {atom: idx for idx, atom in self._id_to_atom.items()}

    @property
    def var_count(self) -> int:
        return len(self._atom_to_id)

    @property
    def max_var(self) -> int:
        return max(self._id_to_atom) if self._id_to_atom else 0

    def __contains__(self, smt_atom: FNode) -> bool:
        return smt_atom in self._atom_to_id

    def get_id(self, smt_atom: FNode) -> int:
        assert is_atom(smt_atom)
        idx = self._atom_to_id.get(smt_atom)
        if idx is None:
            idx = len(self._atom_to_id) + 1
            self._atom_to_id[smt_atom] = idx
            self._id_to_atom[idx] = smt_atom
        return idx

    def get_atom(self, idx: int) -> FNode:
        if idx <= 0:
            raise ValueError(f"expected positive idx, got {idx}")
        return self._id_to_atom[idx]

    def to_dict(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for atom, idx in self._atom_to_id.items():
            script = smtlibscript_from_formula(atom)
            buf = StringIO()
            script.serialize(buf, daggify=False)
            result[buf.getvalue()] = idx
        return result

    @classmethod
    def from_dict(cls, data: dict[str, int], env: Environment | None = None) -> Abstractor:
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
