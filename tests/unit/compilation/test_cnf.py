from unittest.mock import patch

import pytest
import z3
from pysmt.environment import Environment, get_env
from pysmt.shortcuts import FALSE, TRUE, And, Not, Or, Symbol
from pysmt.typing import REAL

from tddnnf.compilation.cnf import CNFConverter
from tddnnf.core.abstraction import Abstractor


@pytest.mark.parametrize("kind, expected", [("true", []), ("false", [[]]), ("unit", [[7]]), ("negative", [[-7]])])
def test_cnf_constants_and_units(env: Environment, kind: str, expected: list[list[int]]):
    p = Symbol("p")
    phi = {"true": TRUE(), "false": FALSE(), "unit": p, "negative": Not(p)}[kind]
    converter = CNFConverter()
    assert converter.convert(phi, {p: 7}) == (expected, 7)


@pytest.mark.parametrize("value, expected", [(True, []), (False, [[]])])
def test_cnf_constants_without_original_atoms(env: Environment, value: bool, expected: list[list[int]]):
    converter = CNFConverter()
    assert converter.convert(TRUE() if value else FALSE(), {}) == (expected, 0)


def test_cnf_preserves_proxy_ids_after_simplification(env: Environment):
    p, q, unused = (Symbol(name) for name in ("p", "q", "unused"))
    ids = {p: 2, q: 5, unused: 9}
    converter = CNFConverter()
    assert converter.convert(And(Or(p, Not(p)), q), ids) == ([[5]], 9)
    assert ids == {p: 2, q: 5, unused: 9}


@pytest.mark.parametrize("inactive", [False, True])
@pytest.mark.parametrize("fail", [False, True])
def test_cnf_environment_isolation(env: Environment, inactive: bool, fail: bool):
    source = Environment() if inactive else env
    mgr = source.formula_manager
    x = mgr.Symbol("x", REAL)
    # Z3 would rewrite these equivalent theory atoms if they reached the tactics.
    a = mgr.LE(x, mgr.Real(0))
    b = mgr.LE(mgr.Plus(x, mgr.Real(1)), mgr.Real(1))
    reflexive = mgr.Equals(x, x)
    phi = mgr.And(a, mgr.Not(b), reflexive)
    ids = {a: 1, b: 2, reflexive: 3}
    abstractor = Abstractor({idx: atom for atom, idx in ids.items()})
    original = dict(abstractor.atom_to_id)
    atoms = source.ao.get_atoms(phi)
    symbols = set(mgr.get_all_symbols())
    converter = CNFConverter()
    if fail:
        with patch("tddnnf.compilation.cnf.z3.Then", side_effect=RuntimeError("tactic failed")):
            with pytest.raises(RuntimeError, match="tactic failed"):
                converter.convert(phi, ids)
    else:
        clauses, count = converter.convert(phi, ids)
        assert set(map(tuple, clauses)) == {(1,), (-2,), (3,)}
        assert count == 3
    assert get_env() is env
    assert source.ao.get_atoms(phi) == atoms
    assert ids == original == dict(abstractor.atom_to_id)
    assert symbols == set(mgr.get_all_symbols())
    # Conversion can be retried successfully, even after a failure.
    assert converter.convert(phi, ids)[1] == 3
    assert get_env() is env
    assert symbols == set(mgr.get_all_symbols())


@pytest.mark.parametrize("kind", ["undeclared", "duplicate", "nonpositive", "nonatom"])
def test_cnf_validates_mapping(env: Environment, kind: str):
    p, q = Symbol("p"), Symbol("q")
    ids = {"undeclared": {}, "duplicate": {p: 1, q: 1}, "nonpositive": {p: 0}, "nonatom": {And(p, q): 1}}[kind]
    with pytest.raises(ValueError):
        CNFConverter().convert(p, ids)
    assert get_env() is env


def test_cnf_auxiliaries_follow_all_original_ids(env: Environment):
    atoms = [Symbol(f"p{i}") for i in range(11)]
    phi = Or(*(And(*atoms[i : i + 2]) for i in range(0, 10, 2)))
    ids = {atom: 3 * i for i, atom in enumerate(atoms, 1)}
    converter = CNFConverter()
    clauses, count = converter.convert(phi, ids)
    assert count > max(ids.values())
    assert any(abs(lit) > max(ids.values()) for clause in clauses for lit in clause)
    assert {abs(lit) for clause in clauses for lit in clause} <= set(ids.values()) | set(
        range(max(ids.values()) + 1, count + 1)
    )
    # Check the projected CNF with an independent solver for every original assignment.
    variables = {i: z3.Bool(f"v{i}") for i in range(1, count + 1)}
    solver = z3.Solver()
    solver.add(*(z3.Or(*(variables[abs(lit)] if lit > 0 else z3.Not(variables[-lit]) for lit in c)) for c in clauses))
    for bits in range(1 << 10):
        assumptions = [variables[ids[a]] == bool(bits & (1 << i)) for i, a in enumerate(atoms[:10])]
        expected = any(bits & (3 << i) == 3 << i for i in range(0, 10, 2))
        assert (solver.check(*assumptions) == z3.sat) == expected
