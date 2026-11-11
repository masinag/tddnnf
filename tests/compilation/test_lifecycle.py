"""Compilation and normalizer cleanup on close, body exceptions, and allocation failures."""

from unittest.mock import Mock

import pytest

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.normalization.normalizer import NormalizerWalker


@pytest.mark.parametrize("session_type", [TheoryCompilation, NormalizerWalker])
def test_session_lifecycle(mgr, session_type):
    session = session_type(mgr.TRUE(), env=mgr.env) if session_type is TheoryCompilation else session_type(mgr.env)
    with pytest.raises(LookupError), session:
        raise LookupError("body failure")
    session.close()
    with pytest.raises(RuntimeError, match="closed"):
        session.normalize(mgr.TRUE())
    with pytest.raises(RuntimeError, match="closed"):
        session.__enter__()
    if session_type is TheoryCompilation:
        with pytest.raises(RuntimeError, match="closed"):
            session.compile_treduced(BddCompiler(), [])


def test_partial_initialization_cleanup(mgr, monkeypatch):
    solver = Mock()
    solver.converter = Mock()
    monkeypatch.setattr(mgr.env.factory, "Solver", Mock(return_value=solver))
    with pytest.raises(ValueError, match="Projection entries"):
        TheoryCompilation(mgr.TRUE(), project_on=[mgr.TRUE()], env=mgr.env)
    solver.exit.assert_called_once()

    # Failure while reading the newly allocated solver's converter also cleans up.
    class BrokenSolver:
        exit = Mock()

        @property
        def converter(self):
            raise RuntimeError("converter failure")

    broken = BrokenSolver()
    monkeypatch.setattr(mgr.env.factory, "Solver", Mock(return_value=broken))
    with pytest.raises(RuntimeError, match="converter failure"):
        NormalizerWalker(mgr.env)
    broken.exit.assert_called_once()
    monkeypatch.setattr(mgr.env.factory, "Solver", Mock(side_effect=RuntimeError("allocation failure")))
    with pytest.raises(RuntimeError, match="allocation failure"):
        TheoryCompilation(mgr.TRUE(), env=mgr.env)
