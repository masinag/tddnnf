from collections.abc import Generator
from contextlib import nullcontext
from pathlib import Path
from typing import Self

import pytest
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.typing import INT

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import DagSize
from tddnnf.core.theory_compiled_target import TheoryCompiledTarget


class RecordingTarget:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[FNode] | None]] = []

    def dag_size(self) -> DagSize:
        raise NotImplementedError

    def save(self, directory: Path) -> None:
        raise NotImplementedError

    @classmethod
    def load(cls, directory: Path) -> Self:
        raise NotImplementedError

    def to_pysmt(self, abstr: Abstractor, mgr: FormulaManager) -> FNode:
        raise NotImplementedError


class RecordingEngine:
    def __init__(self, target):
        self.calls = target.target.calls
        self.assignments = [{target.atoms[0]: True}, {target.atoms[0]: False}]

    def close(self):
        pass

    def is_satisfiable(self, assumptions=None):
        self.calls.append(("is_satisfiable", assumptions))
        return False

    def count_truth_assignments(self, assumptions=None):
        self.calls.append(("count_truth_assignments", assumptions))
        return 17

    def is_valid(self):
        return False

    def entails_clause(self, clause):
        self.calls.append(("entails_clause", clause))
        return True

    def is_implicant(self, cube):
        self.calls.append(("is_implicant", cube))
        return False

    def enumerate_truth_assignments(self) -> Generator[dict[FNode, bool], None, None]:
        yield from self.assignments


@pytest.fixture
def target(env) -> TheoryCompiledTarget[RecordingTarget]:
    mgr = env.formula_manager
    p, q = mgr.Symbol("p"), mgr.Symbol("q")
    n = mgr.Symbol("n", INT)
    atoms = [p, q, mgr.GE(n, mgr.Int(2)), mgr.LT(n, mgr.Int(5))]
    return TheoryCompiledTarget(RecordingTarget(), Abstractor(dict(enumerate(atoms, 1))), atoms, env=env)


def test_public_queries_return_engine_results(target):
    p = target.atoms[0]
    with target.queries(RecordingEngine) as session:
        assert session.is_satisfiable() is False
        assert session.count_truth_assignments(None) == 17
        assert session.is_satisfiable([]) is False
        assert session.is_valid() is False
        assert session.entails_clause(p) is True
        assert session.is_implicant(p) is False
        assert list(session.enumerate_truth_assignments()) == [{p: True}, {p: False}]


def test_arithmetic_alignment_and_polarity(target):
    mgr = target.env.formula_manager
    n = mgr.Symbol("n", INT)
    scaled = mgr.Times(mgr.Int(2), n)
    lower, upper = target.atoms[2:]
    literals = [
        mgr.GE(scaled, mgr.Int(4)),
        mgr.Not(mgr.GE(scaled, mgr.Int(4))),
        mgr.LT(scaled, mgr.Int(10)),
        mgr.GE(n, mgr.Int(5)),
    ]
    with target.queries(RecordingEngine) as session:
        session.is_satisfiable(literals)
    assert target.target.calls == [("is_satisfiable", [lower, mgr.Not(lower), upper, mgr.Not(upper)])]


def test_nested_clauses_and_cubes_preserve_order_and_duplicates(target):
    mgr = target.env.formula_manager
    p, q = target.atoms[:2]
    with target.queries(RecordingEngine) as session:
        session.entails_clause(mgr.Or(p, mgr.Or(mgr.Not(q), p)))
        session.is_implicant(mgr.And(p, mgr.And(mgr.Not(q), p)))
    assert target.target.calls == [
        ("entails_clause", [p, mgr.Not(q), p]),
        ("is_implicant", [p, mgr.Not(q), p]),
    ]


def test_constants_are_accepted(target):
    mgr = target.env.formula_manager
    with target.queries(RecordingEngine) as session:
        assert session.count_truth_assignments([mgr.TRUE(), mgr.FALSE()]) == 17
        assert session.entails_clause(mgr.TRUE()) is True
        assert session.is_implicant(mgr.FALSE()) is False


def test_invalid_inputs_never_reach_engine(target):
    mgr = target.env.formula_manager
    p, q = target.atoms[:2]
    unknown = mgr.Symbol("undeclared")
    with target.queries(RecordingEngine) as session:
        for operation, query in (
            (session.is_satisfiable, [mgr.And(p, q)]),
            (session.count_truth_assignments, [mgr.FALSE(), unknown]),
            (session.entails_clause, mgr.Or(mgr.TRUE(), unknown)),
            (session.is_implicant, mgr.And(mgr.FALSE(), unknown)),
            (session.is_satisfiable, [42]),
            (session.entails_clause, 42),
        ):
            with pytest.raises(ValueError):
                operation(query)
    assert target.target.calls == []


@pytest.mark.parametrize("exceptional", [False, True])
def test_context_exit_closes_session(target, exceptional):
    session = target.queries(RecordingEngine)
    with pytest.raises(ValueError) if exceptional else nullcontext():
        with session as entered:
            assert entered is session
            if exceptional:
                raise ValueError("context failure")
    with pytest.raises(RuntimeError):
        session.is_valid()
    session.close()
    with pytest.raises(RuntimeError):
        session.count_truth_assignments()
    with pytest.raises(RuntimeError):
        session.enumerate_truth_assignments()
    with pytest.raises(RuntimeError):
        with session:
            pytest.fail("Closed session entered")


def test_sessions_over_same_target_are_independent(target):
    with target.queries(RecordingEngine) as first, target.queries(RecordingEngine) as second:
        first.close()
        assert second.count_truth_assignments() == 17


def test_enumerations_remain_independent_after_exhaustion_and_close(target):
    p = target.atoms[0]
    with target.queries(RecordingEngine) as session:
        first = session.enumerate_truth_assignments()
        second = session.enumerate_truth_assignments()
        third = session.enumerate_truth_assignments()
        assert next(first) == next(second) == next(third) == {p: True}
        assert list(first) == [{p: False}]
        third.close()
        assert list(third) == []
        assert list(second) == [{p: False}]
        assert session.count_truth_assignments() == 17


def test_session_close_stops_active_and_unstarted_enumerations(target):
    with target.queries(RecordingEngine) as session:
        first = session.enumerate_truth_assignments()
        second = session.enumerate_truth_assignments()
        unstarted = session.enumerate_truth_assignments()
        next(first)
        next(second)
        session.close()
        assert list(first) == list(second) == list(unstarted) == []
