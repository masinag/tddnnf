from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Generic

from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import T_Target


class TheoryCompiledTarget(Generic[T_Target]):
    """A compiled target paired with its SMT-to-Boolean abstraction."""

    def __init__(self, target: T_Target, abstr: Abstractor, care_vars: list[FNode]) -> None:
        self.target = target
        self.abstr = abstr
        self.care_vars = care_vars

    def save(self, directory: Path) -> None:
        """Serialize the abstraction and delegate target persistence."""
        directory.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "abstraction": self.abstr.to_dict(),
            "care_var_ids": [self.abstr.get_id(a) for a in self.care_vars],
        }
        (directory / "abstraction.json").write_text(json.dumps(payload, indent=2))
        self.target.save(directory)

    def to_pysmt(self, mgr: FormulaManager) -> FNode:
        return self.target.to_pysmt(self.abstr, mgr)

    @classmethod
    def load(cls, directory: Path, target_type: type[T_Target]) -> TheoryCompiledTarget[T_Target]:
        """Reconstruct a container from a directory and the target's load classmethod."""
        payload = json.loads((directory / "abstraction.json").read_text())
        abstr = Abstractor.from_dict(payload["abstraction"])
        care_var_ids: list[int] = payload["care_var_ids"]
        target = target_type.load(directory)
        care_vars = [abstr.get_atom(i) for i in care_var_ids]
        return cls(target, abstr, care_vars)
