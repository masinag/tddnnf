from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic

from pysmt.environment import Environment, get_env
from pysmt.fnode import FNode

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import DagSize, T_Target

if TYPE_CHECKING:
    from tddnnf.queries import CuddReasoner, DdnnifeReasoner, QuerySession, SddReasoner


class TheoryCompiledTarget(Generic[T_Target]):
    """A representation bound to its abstraction, vocabulary, and SMT environment."""

    def __init__(
        self,
        target: T_Target,
        abstr: Abstractor,
        projection_atoms: Sequence[FNode],
        env: Environment | None = None,
    ) -> None:
        self._target = target
        self._abstr = abstr
        self._projection_atoms = tuple(projection_atoms)
        self._env = env if env is not None else get_env()

    @property
    def target(self) -> T_Target:
        return self._target

    @property
    def abstr(self) -> Abstractor:
        return self._abstr

    @property
    def projection_atoms(self) -> tuple[FNode, ...]:
        return self._projection_atoms

    @property
    def env(self) -> Environment:
        return self._env

    def queries(self, reasoner: CuddReasoner | SddReasoner | DdnnifeReasoner) -> QuerySession:
        """Open an independent query session with a compatible native reasoner."""
        from tddnnf.queries import QuerySession

        return QuerySession(self, reasoner)

    def dag_size(self) -> DagSize:
        return self.target.dag_size()

    def save(self, directory: Path) -> None:
        """Serialize the abstraction and delegate target persistence."""
        directory.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "abstraction": self.abstr.to_dict(),
            "projection_atom_ids": [self.abstr.get_id(a) for a in self.projection_atoms],
        }
        (directory / "abstraction.json").write_text(json.dumps(payload, indent=2))
        self.target.save(directory)

    def to_pysmt(self) -> FNode:
        return self.target.to_pysmt(self.abstr, self.env.formula_manager)

    @classmethod
    def load(
        cls,
        directory: Path,
        target_type: type[T_Target],
        env: Environment | None = None,
    ) -> TheoryCompiledTarget[T_Target]:
        """Reconstruct a container from a directory and the target's load classmethod."""
        env = env if env is not None else get_env()
        payload = json.loads((directory / "abstraction.json").read_text())
        abstr = Abstractor.from_dict(payload["abstraction"], env=env)
        projection_atom_ids: list[int] = payload["projection_atom_ids"]
        target = target_type.load(directory)
        projection_atoms = [abstr.get_atom(i) for i in projection_atom_ids]
        return cls(target, abstr, projection_atoms, env=env)
