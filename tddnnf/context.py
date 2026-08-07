from __future__ import annotations

from collections.abc import Iterable

from pysmt.fnode import FNode

from tddnnf.normalization.normalizer import NormalizerWalker


class KCMTContext:
    """Normalization context for a KCMT workflow."""

    def __init__(
        self,
        phi: FNode | None = None,
        project_on: Iterable[FNode] | None = None,
        normalizer: NormalizerWalker | None = None,
    ) -> None:
        """Create a context and normalize its formula and projection atoms.

        Args:
            phi: Formula used by the KCMT workflow.
            project_on: Atoms retained by compilation. Defaults to atoms in
                normalized ``phi`` when omitted.
            normalizer: Normalizer instance to use. A new one is created when
                omitted.
        """
        self._normalizer = normalizer or NormalizerWalker()
        self.phi = self.normalize(phi) if phi is not None else None
        if project_on is not None:
            self.project_on = [self._normalize_atom(atom) for atom in project_on]
        elif self.phi is not None:
            self.project_on = [self._normalize_atom(atom) for atom in self.phi.get_atoms()]
        else:
            self.project_on = None

    def normalize(self, formula: FNode) -> FNode:
        """Normalize a formula."""
        return self._normalizer.normalize(formula)

    def _normalize_atom(self, atom: FNode) -> FNode:
        """Normalize an atom to its positive canonical representation."""
        normalized = self.normalize(atom)
        return normalized.arg(0) if normalized.is_not() else normalized
