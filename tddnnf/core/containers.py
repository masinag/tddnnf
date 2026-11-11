from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Generic

from pysmt.environment import Environment, get_env
from pysmt.fnode import FNode

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import DagSize, QueryEngine, T_Target
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
        """Write and validate a versioned artifact before publishing it."""
        from tddnnf.core.persistence import publication, read_json, write_native

        with publication(directory) as stage:
            payload = {
                "abstraction": self.abstr.to_dict(),
                "projection_atom_ids": [self.abstr.atom_to_id[a] for a in self.projection_atoms],
            }
            (stage / "abstraction.json").write_text(json.dumps(payload, indent=2))
            write_native(self.target, stage)
            metadata = read_json(stage / "metadata.json")
            metadata["files"].append("abstraction.json")
            (stage / "metadata.json").write_text(json.dumps(metadata, indent=2))
            self.load(stage, env=self.env)

    def to_pysmt(self) -> FNode:
        return self.target.to_pysmt(self.abstr, self.env.formula_manager)

    @classmethod
    def load(
        cls,
        directory: Path,
        env: Environment | None = None,
    ) -> TheoryCompiledTarget:
        """Infer the representation from versioned metadata and bind atoms to env."""
        from tddnnf.core.persistence import load_native

        abstr, projection, env = cls._read_data(directory, env)
        return cls(load_native(directory), abstr, projection, env=env)

    @staticmethod
    def _read_data(directory: Path, env: Environment | None = None):
        """Validate container data without expanding or importing the native graph."""
        from tddnnf.core.persistence import integer, metadata, read_json, validate_native
        from tddnnf.core.pysmt_utils import is_atom

        directory = Path(directory)
        env = env if env is not None else get_env()
        data = metadata(directory)
        if "abstraction.json" not in data["files"]:
            raise ValueError("Missing abstraction declaration")
        payload = read_json(directory / "abstraction.json")
        mapping = payload.get("abstraction")
        if not isinstance(mapping, dict):
            raise ValueError("Invalid abstraction")
        ids = list(mapping.values())
        for idx in ids:
            integer(idx, 1)
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate abstraction IDs")
        abstr = Abstractor.from_dict(mapping, env=env)
        if abstr.var_count != len(ids) or any(not is_atom(a) for a in abstr.atom_to_id):
            raise ValueError("Abstraction must contain distinct atoms")
        projection = payload.get("projection_atom_ids")
        if not isinstance(projection, list):
            raise ValueError("Invalid ordered projection")
        for idx in projection:
            integer(idx, 1)
        if len(projection) != len(set(projection)) or not set(projection) <= set(ids):
            raise ValueError("Invalid projection IDs")
        if "care_var_ids" in payload and payload["care_var_ids"] != projection:
            raise ValueError("Conflicting projection keys")
        support = validate_native(directory, data)
        if not support <= set(projection):
            raise ValueError("Native support is outside the active projection")
        if data["representation"] == "ddnnf":
            if {int(k) for k in data["remapping"]} != set(projection):
                canonical_constant = (directory / "circuit.nnf").read_text() in ("t 1\n", "f 1\n")
                if data["var_count"] or not canonical_constant:
                    raise ValueError("d4 mapping must cover the active projection")
        elif data["representation"] == "obdd":
            if not {f"b{i}" for i in projection} <= set(data["variable_order"]):
                raise ValueError("Active projection absent from native OBDD universe")
        elif any(i > data["var_count"] for i in projection):
            raise ValueError("Active projection absent from native SDD universe")
        return abstr, [abstr.get_atom(i) for i in projection], env
