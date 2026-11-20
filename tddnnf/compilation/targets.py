from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, Protocol, Self, TypeVar, runtime_checkable

from pysmt.environment import Environment, get_env
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.persistence import read_json, saving_to
from tddnnf.core.pysmt_utils import owns_dags


@dataclass(frozen=True)
class DagSize:
    """DAG size as vertices and edges."""

    vertices: int
    edges: int


@runtime_checkable
class PropCompiledTarget(Protocol):
    """A propositional formula compiled into some target language (d-DNNF, SDD, OBDD, ...)."""

    def dag_size(self) -> DagSize:
        """Return the size of the formula DAG."""
        ...

    def save(self, directory: Path) -> None:
        """Persist the target to disk.

        Args:
            directory: Where to store the target.
        """
        ...

    @classmethod
    def load(cls, directory: Path) -> Self:
        """Load the target from disk.

        Args:
            directory: Where the target is stored.

        Returns:
            PropCompiledTarget: The loaded target.
        """
        ...

    def to_pysmt(self, abstr: Abstractor, mgr: FormulaManager) -> FNode:
        """Reconstruct the formula from the compiled DAG.

        Args:
            abstr: Mapping from node index to SMT atom.
            mgr: Formula manager to create the FNodes.

        Returns:
            FNode: The target as a PySMT formula.
        """
        ...


T_Target = TypeVar("T_Target", bound=PropCompiledTarget)
T_Target_co = TypeVar("T_Target_co", bound=PropCompiledTarget, covariant=True)


class TheoryCompiledTarget(Generic[T_Target]):
    """An SMT-level NNF-compiled formula."""

    def __init__(
        self,
        target: T_Target,
        abstr: Abstractor,
        atoms: Sequence[FNode],
        env: Environment | None = None,
    ) -> None:
        """Construct the SMT target.

        Args:
            target: The compiled Boolean abstraction.
            abstr: The mapping from nodes to IDs representing the abstractions.
            atoms: The superset of atoms the target is built from.
            env: The PySMT environment owning the atoms.
        """
        self._target = target
        self._abstr = abstr
        self._atoms = tuple(atoms)
        self._env = env if env is not None else get_env()
        assert owns_dags(self._env, abstr.id_to_atom.values()), "Abstraction must belong to the selected environment"
        assert owns_dags(self._env, self._atoms), "Atoms must belong to the selected environment"

    @property
    def target(self) -> T_Target:
        return self._target

    @property
    def abstr(self) -> Abstractor:
        return self._abstr

    @property
    def atoms(self) -> tuple[FNode, ...]:
        return self._atoms

    @property
    def env(self) -> Environment:
        return self._env

    def dag_size(self) -> DagSize:
        return self.target.dag_size()

    def save(self, directory: Path) -> None:
        """Serialize the target on disk.

        Args:
            directory: Where to store the target.
        """

        with saving_to(directory) as temporary_directory:
            self.target.save(temporary_directory)
            payload = {
                "abstraction": self.abstr.to_dict(),
                "atom_ids": [self.abstr.atom_to_id[a] for a in self.atoms],
            }
            (temporary_directory / "abstraction.json").write_text(json.dumps(payload, indent=2))
            data = read_json(temporary_directory / "metadata.json")
            data["files"].append("abstraction.json")
            (temporary_directory / "metadata.json").write_text(json.dumps(data, indent=2))

    def to_pysmt(self) -> FNode:
        return self.target.to_pysmt(self.abstr, self.env.formula_manager)

    @classmethod
    def load[T_Loaded: PropCompiledTarget](
        cls: type[TheoryCompiledTarget[T_Loaded]],
        directory: Path,
        target_type: type[T_Loaded],
        env: Environment | None = None,
    ) -> TheoryCompiledTarget[T_Loaded]:
        """Load a target from disk.

        Args:
            directory: Where the target is stored.
            target_type: Expected type of the propositional target being loaded.
            env: The PySMT environment to build the atoms from.

        Returns:
            TheoryCompiledTarget[T_Loaded]: The loaded target.
        """
        directory = Path(directory)
        env = env if env is not None else get_env()
        target = target_type.load(directory)
        payload = read_json(directory / "abstraction.json")
        abstr = Abstractor.from_dict(payload["abstraction"], env=env)
        atoms = [abstr.get_atom(i) for i in payload["atom_ids"]]
        return cls(target, abstr, atoms=atoms, env=env)
