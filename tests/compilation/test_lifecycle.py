"""Compilation and normalizer cleanup on close, body exceptions, and allocation failures."""

from unittest.mock import Mock

import pytest

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.normalization.normalizer import NormalizerWalker


def test_compilation_lifecycle(mgr):
    session = TheoryCompilation(mgr.TRUE(), env=mgr.env)
    with pytest.raises(LookupError), session:
        raise LookupError("body failure")
    session.close()
    with pytest.raises(RuntimeError, match="closed"):
        session.normalize(mgr.TRUE())
    with pytest.raises(RuntimeError, match="closed"):
        session.__enter__()
    with pytest.raises(RuntimeError, match="closed"):
        session.compile_treduced(BddCompiler(), [])


def test_invalid_projection_closes_allocated_solver(mgr, monkeypatch):
    solver = Mock()
    solver.converter = Mock()
    monkeypatch.setattr(mgr.env.factory, "Solver", Mock(return_value=solver))
    with pytest.raises(ValueError, match="Vocabulary entries"):
        TheoryCompilation(mgr.TRUE(), atoms=[mgr.TRUE()], env=mgr.env)
    solver.exit.assert_called_once()


def test_converter_access_failure_closes_allocated_solver(mgr, monkeypatch):
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


def test_solver_allocation_failure_propagates(mgr, monkeypatch):
    monkeypatch.setattr(mgr.env.factory, "Solver", Mock(side_effect=RuntimeError("allocation failure")))
    with pytest.raises(RuntimeError, match="allocation failure"):
        TheoryCompilation(mgr.TRUE(), env=mgr.env)
