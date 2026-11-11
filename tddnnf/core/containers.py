from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Generic

from pysmt.environment import Environment, get_env
from pysmt.fnode import FNode

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import DagSize, PropCompiledTarget, QueryEngine, T_Target
from tddnnf.core.persistence import metadata, read_json, saving_to
from tddnnf.queries.session import QuerySession


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

    def queries(self, engine_type: type[QueryEngine[T_Target]]) -> QuerySession[T_Target]:
        """Open an independent session using the explicitly selected engine class."""
        return QuerySession(self, engine_type)

    def dag_size(self) -> DagSize:
        return self.target.dag_size()

    def save(self, directory: Path) -> None:
        """Serialize package-owned state into a versioned artifact."""

        with saving_to(directory) as temporary_directory:
            self.target.save(temporary_directory)
            payload = {
                "abstraction": self.abstr.to_dict(),
                "projection_atom_ids": [self.abstr.atom_to_id[a] for a in self.projection_atoms],
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
        metadata(directory)
        target = target_type.load(directory)
        payload = read_json(directory / "abstraction.json")
        abstr = Abstractor.from_dict(payload["abstraction"], env=env)
        projection = [abstr.get_atom(i) for i in payload["projection_atom_ids"]]
        return cls(target, abstr, projection, env=env)
