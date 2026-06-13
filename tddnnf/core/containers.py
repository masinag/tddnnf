from __future__ import annotations

import json
from pathlib import Path
from typing import Generic

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import T_Target


class TheoryCompiledTarget(Generic[T_Target]):
    """A compiled target paired with its SMT-to-Boolean abstraction."""

    def __init__(self, target: T_Target, abstr: Abstractor) -> None:
        self.target = target
        self.abstr = abstr

    def save(self, directory: Path) -> None:
        """Serialize the abstraction and delegate target persistence."""
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "abstraction.json").write_text(json.dumps(self.abstr.to_dict(), indent=2))
        self.target.save(directory)

    @classmethod
    def load(
        cls,
        directory: Path,
        target_type: type[T_Target],
    ) -> TheoryCompiledTarget[T_Target]:
        """Reconstruct a container from a directory and the target's load classmethod."""
        abstr_data = json.loads((directory / "abstraction.json").read_text())
        abstr = Abstractor.from_dict(abstr_data)
        target = target_type.load(directory)
        return cls(target, abstr)
