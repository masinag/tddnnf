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
            directory: where to store the target.
        """
        ...

    @classmethod
    def load(cls, directory: Path) -> Self:
        """Load the target from disk.

        Args:
            directory: where the target is stored.
        """
        ...

    def to_pysmt(self, abstr: Abstractor, mgr: FormulaManager) -> FNode:
        """Reconstruct the formula from the compiled DAG.

        Args:
            abstr: mapping from node index to SMT atom.
            mgr: formula manager to create the FNodes.
        """
        ...


T_Target = TypeVar("T_Target", bound=PropCompiledTarget)
T_Target_co = TypeVar("T_Target_co", bound=PropCompiledTarget, covariant=True)


class TheoryCompiledTarget(Generic[T_Target]):
    """A representation bound to its abstraction, vocabulary, and SMT environment."""

    def __init__(
        self,
        target: T_Target,
        abstr: Abstractor,
        atoms: Sequence[FNode],
        env: Environment | None = None,
    ) -> None:
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
        """Serialize package-owned state into a versioned artifact."""

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
        cls: type[TheoryCompiledTarget],
        directory: Path,
        target_type: type[T_Loaded],
        env: Environment | None = None,
    ) -> TheoryCompiledTarget[T_Loaded]:
        """Load with the selected backend and bind atoms to env."""
        directory = Path(directory)
        env = env if env is not None else get_env()
        target = target_type.load(directory)
        payload = read_json(directory / "abstraction.json")
        abstr = Abstractor.from_dict(payload["abstraction"], env=env)
        atoms = [abstr.get_atom(i) for i in payload["atom_ids"]]
        return cls(target, abstr, atoms=atoms, env=env)
