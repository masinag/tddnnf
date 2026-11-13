"""Direct engines accept flat literals and validate vocabulary before applying shortcuts."""

import pytest
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import PropCompiler


@pytest.mark.parametrize(
    ("polarities", "expected_count"),
    [(None, 3), ([], 3), ([True, True], 2), ([True, False], 0), ([False], 1)],
    ids=["none", "empty", "duplicate", "contradictory", "negative"],
)
def test_normalized_assumptions(
    engine_factory,
    mgr: FormulaManager,
    compiler: PropCompiler,
    a: FNode,
    b: FNode,
    polarities: list[bool] | None,
    expected_count: int,
) -> None:
    abstr = Abstractor({1: a, 2: b})
    target = compiler.compile(mgr.Or(a, b), abstr, all_atoms=[a, b])
    engine = engine_factory(TheoryCompiledTarget(target, abstr, projection_atoms=[a, b], env=mgr.env))
    assumptions = None if polarities is None else [a if positive else mgr.Not(a) for positive in polarities]
    assert engine.is_satisfiable(assumptions) == (expected_count > 0)
    assert engine.count_truth_assignments(assumptions) == expected_count


@pytest.mark.parametrize(
    "case,entailed,implicant,count",
    [
        ("empty", False, False, 1),
        ("true", True, False, 1),
        ("false", False, True, 0),
        ("not-true", False, True, 0),
        ("not-false", True, False, 1),
        ("duplicate", True, False, 1),
        ("complementary", True, True, 0),
        ("both", True, True, 1),
        ("false-atom", True, True, 0),
        ("true-negative", True, False, 0),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_literal_truth_table(engine, mgr, a, b, case, entailed, implicant, count):
    literals = {
        "empty": [],
        "true": [mgr.TRUE()],
        "false": [mgr.FALSE()],
        "not-true": [mgr.Not(mgr.TRUE())],
        "not-false": [mgr.Not(mgr.FALSE())],
        "duplicate": [a, a],
        "complementary": [a, mgr.Not(a)],
        "both": [a, b],
        "false-atom": [mgr.FALSE(), a],
        "true-negative": [mgr.TRUE(), mgr.Not(a)],
    }[case]
    assert engine.entails_clause(literals) == entailed
    assert engine.is_implicant(literals) == implicant
    assert engine.is_satisfiable(literals) == (count > 0)
    assert engine.count_truth_assignments(literals) == count


@pytest.mark.parametrize("tail", ["unknown", "compound"])
@pytest.mark.parametrize("prefix", ["true", "false", "complementary"])
@pytest.mark.parametrize("operation", ["entails_clause", "is_implicant", "is_satisfiable", "count_truth_assignments"])
def test_validates_before_shortcuts(engine, mgr, a, b, c, tail, prefix, operation):
    literals = {"true": [mgr.TRUE()], "false": [mgr.FALSE()], "complementary": [a, mgr.Not(a)]}[prefix]
    literals.append(c if tail == "unknown" else mgr.Iff(a, b))
    with pytest.raises(ValueError):
        getattr(engine, operation)(literals)


@pytest.mark.parametrize("operation", ["is_satisfiable", "count_truth_assignments", "entails_clause", "is_implicant"])
def test_unknown_literal(engine, mgr, c, operation):
    with pytest.raises(ValueError, match="not .*projection"):
        getattr(engine, operation)([c])


def test_is_implicant_invalid_input(engine, mgr, a, b):
    with pytest.raises(ValueError):
        engine.is_implicant([mgr.Or(a, b)])


def test_projected_assumption_on_forgotten_var_raises(
    engine_factory,
    mgr: FormulaManager,
    compiler: PropCompiler,
    a: FNode,
    b: FNode,
    c: FNode,
) -> None:
    abstr = Abstractor({1: a, 2: b, 3: c})
    target = compiler.compile(mgr.And(a, mgr.Or(b, c)), abstr, all_atoms=[a, b, c], exists_atoms=[c])
    engine = engine_factory(TheoryCompiledTarget(target, abstr, projection_atoms=[a, b], env=mgr.env))
    with pytest.raises(ValueError, match="not .*projection"):
        engine.is_satisfiable(assumptions=[c])
    with pytest.raises(ValueError, match="not .*projection"):
        engine.count_truth_assignments(assumptions=[c])
