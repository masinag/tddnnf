from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic

from pysmt.environment import Environment, get_env
from pysmt.fnode import FNode

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import DagSize, T_Target


@dataclass(frozen=True, init=False)
class TheoryCompiledTarget(Generic[T_Target]):
    """A representation bound to its abstraction, vocabulary, and SMT environment."""

    target: T_Target
    abstr: Abstractor
    projection_atoms: tuple[FNode, ...]
    env: Environment

    def __init__(
        self,
        target: T_Target,
        abstr: Abstractor,
        projection_atoms: Sequence[FNode],
        env: Environment | None = None,
    ) -> None:
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "abstr", abstr)
        object.__setattr__(self, "projection_atoms", tuple(projection_atoms))
        object.__setattr__(self, "env", env if env is not None else get_env())

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
