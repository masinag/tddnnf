from __future__ import annotations

import json
from pathlib import Path
from typing import Generic

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import T_Target


class TheoryCompiledTarget(Generic[T_Target]):
    """A compiled target paired with its SMT-to-Boolean abstraction context."""

    def __init__(self, target: T_Target, context: Abstractor) -> None:
        self.target = target
        self.context = context

    def save(self, directory: Path) -> None:
        """Serialize the abstraction context and delegate target persistence."""
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "context.json").write_text(json.dumps(self.context.to_dict(), indent=2))
        self.target.save(directory)

    @classmethod
    def load(
        cls,
        directory: Path,
        target_type: type[T_Target],
    ) -> TheoryCompiledTarget[T_Target]:
        """Reconstruct a container from a directory and the target's load classmethod."""
        context_data = json.loads((directory / "context.json").read_text())
        context = Abstractor.from_dict(context_data)
        target = target_type.load(directory)
        return cls(target, context)
