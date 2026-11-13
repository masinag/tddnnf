from collections.abc import Callable
from contextlib import nullcontext

import pytest
from pysmt.environment import Environment, get_env
from pysmt.exceptions import PysmtTypeError
from pysmt.typing import BOOL, INT, REAL

from tddnnf.core.pysmt_utils import (
    SuspendTypeChecking,
    clause_lits,
    compilation_vocabulary,
    cube_lits,
    get_theory_atoms,
    is_atom,
    is_clause,
    is_cube,
    is_literal,
)


def test_atoms_and_negations(env: Environment) -> None:
    mgr = env.formula_manager
    atoms = (
        mgr.Symbol("p", BOOL),
        mgr.LE(mgr.Symbol("x", REAL), mgr.Real(0)),
        mgr.Equals(mgr.Symbol("n", INT), mgr.Int(1)),
        mgr.TRUE(),
        mgr.FALSE(),
    )
    for atom in atoms:
        assert is_atom(atom)
        assert is_literal(atom) and is_clause(atom) and is_cube(atom)
        negated = mgr.Not(atom)
        assert not is_atom(negated)
        assert is_literal(negated) and is_clause(negated) and is_cube(negated)


def test_compound_classification(env: Environment) -> None:
    mgr = env.formula_manager
    p, q = mgr.Symbol("p", BOOL), mgr.Symbol("q", BOOL)
    relation = mgr.LE(mgr.Symbol("x", REAL), mgr.Real(0))
    for formula, clause, cube in (
        (mgr.Or(p, mgr.Or(mgr.Not(q), relation)), True, False),
        (mgr.And(p, mgr.And(mgr.Not(q), relation)), False, True),
        (mgr.Or(p, mgr.And(q, relation)), False, False),
        (mgr.And(p, mgr.Or(q, relation)), False, False),
        (mgr.Implies(p, q), False, False),
        (mgr.Iff(p, q), False, False),
        (mgr.Not(mgr.Or(p, q)), False, False),
        (mgr.Not(mgr.And(p, q)), False, False),
        (mgr.Symbol("n", INT), False, False),
        (mgr.Int(1), False, False),
    ):
        assert not is_atom(formula) and not is_literal(formula)
        assert is_clause(formula) is clause
        assert is_cube(formula) is cube


def test_get_theory_atoms_preserves_order_constants_and_input(env: Environment) -> None:
    mgr = env.formula_manager
    relation = mgr.LE(mgr.Symbol("x", REAL), mgr.Real(0))
    atoms = [mgr.TRUE(), mgr.Symbol("p", BOOL), relation, mgr.FALSE(), relation]
    original = atoms.copy()
    assert get_theory_atoms(atoms) == [mgr.TRUE(), relation, mgr.FALSE(), relation]
    assert atoms == original
    assert get_theory_atoms([]) == []


@pytest.mark.parametrize("normalize", [clause_lits, cube_lits])
def test_query_literals_deduplicate_without_mutating_inputs(env: Environment, normalize: Callable) -> None:
    mgr = env.formula_manager
    p = mgr.Symbol("p", BOOL)
    relation = mgr.LE(mgr.Symbol("x", REAL), mgr.Real(0))
    projection = [relation, p]
    literals = [mgr.Not(p), relation, mgr.Not(p), relation]
    original = literals.copy()
    assert normalize([], projection) == []
    assert normalize(literals, projection) == [mgr.Not(p), relation]
    assert normalize([p, mgr.Not(p)], projection) is None
    assert normalize([mgr.Not(p), p], projection) is None
    assert literals == original
    assert projection == [relation, p]


def test_query_literal_constants(env: Environment) -> None:
    mgr = env.formula_manager
    p = mgr.Symbol("p", BOOL)
    for constant, clause, cube in (
        (mgr.TRUE(), None, [p]),
        (mgr.FALSE(), [p], None),
        (mgr.Not(mgr.TRUE()), [p], None),
        (mgr.Not(mgr.FALSE()), None, [p]),
    ):
        assert clause_lits([constant, p], [p]) == clause
        assert cube_lits([constant, p], [p]) == cube
    assert clause_lits([mgr.FALSE()], []) == []
    assert cube_lits([mgr.TRUE()], []) == []
    assert clause_lits([mgr.TRUE()], []) is None
    assert cube_lits([mgr.FALSE()], []) is None


@pytest.mark.parametrize("normalize", [clause_lits, cube_lits])
def test_query_literals_reject_invalid_inputs(env: Environment, normalize: Callable) -> None:
    mgr = env.formula_manager
    p, q = mgr.Symbol("p", BOOL), mgr.Symbol("q", BOOL)
    for invalid in (q, mgr.Not(q), mgr.Or(p, q), mgr.Not(mgr.And(p, q)), mgr.Int(1), True):
        with pytest.raises(ValueError):
            normalize([invalid], [p])


def test_query_literals_validate_after_decisive_inputs(env: Environment) -> None:
    mgr = env.formula_manager
    p, q = mgr.Symbol("p", BOOL), mgr.Symbol("q", BOOL)
    for normalize, literals in (
        (clause_lits, [mgr.TRUE(), q]),
        (cube_lits, [mgr.FALSE(), q]),
        (clause_lits, [p, mgr.Not(p), q]),
        (cube_lits, [p, mgr.Not(p), q]),
    ):
        original = literals.copy()
        projection = [p]
        with pytest.raises(ValueError):
            normalize(literals, projection)
        assert literals == original
        assert projection == [p]


def test_compilation_vocabulary_retains_order_and_unused_atoms(env: Environment) -> None:
    mgr = env.formula_manager
    p, q, unused = (mgr.Symbol(name, BOOL) for name in ("p", "q", "unused"))
    relation = mgr.LE(mgr.Symbol("x", REAL), mgr.Real(0))
    declared, quantified = [unused, relation, q, p], [q, unused]
    formula = mgr.And(p, q, relation)
    assert compilation_vocabulary(formula, declared, [], []) == tuple(declared)
    assert compilation_vocabulary(formula, declared, quantified, []) == (relation, p)
    assert compilation_vocabulary(formula, declared, [], quantified) == (relation, p)
    assert compilation_vocabulary(formula, declared, declared, []) == ()
    assert compilation_vocabulary(formula, declared, [], declared) == ()
    assert declared == [unused, relation, q, p]
    assert quantified == [q, unused]
    for constant in (mgr.TRUE(), mgr.FALSE()):
        assert compilation_vocabulary(constant, [], [], []) == ()
        assert compilation_vocabulary(constant, [p], [], []) == (p,)


def test_compilation_vocabulary_rejects_invalid_declarations(env: Environment) -> None:
    mgr = env.formula_manager
    p, q = mgr.Symbol("p", BOOL), mgr.Symbol("q", BOOL)
    for invalid in (mgr.TRUE(), mgr.FALSE(), mgr.Not(p), mgr.And(p, q), mgr.Symbol("n", INT), "p"):
        with pytest.raises(ValueError):
            compilation_vocabulary(p, [p, invalid], [], [])
    for declared, exists, forall in (
        ([p, p], [], []),
        ([p], [p, p], []),
        ([p], [], [p, p]),
        ([p], [mgr.TRUE()], []),
        ([p], [], [mgr.Not(p)]),
        ([p], [q], []),
        ([p], [], [q]),
        ([p, q], [p], [q]),
        ([p], [p], [p]),
    ):
        original = (declared.copy(), exists.copy(), forall.copy())
        with pytest.raises(ValueError):
            compilation_vocabulary(p, declared, exists, forall)
        assert (declared, exists, forall) == original


def test_compilation_vocabulary_requires_formula_atoms(env: Environment) -> None:
    mgr = env.formula_manager
    p, q = mgr.Symbol("p", BOOL), mgr.Symbol("q", BOOL)
    with pytest.raises(ValueError):
        compilation_vocabulary(mgr.And(p, q), [p], [], [])
    with pytest.raises(ValueError):
        compilation_vocabulary(p, [], [], [])


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("exceptional", [False, True])
def test_suspend_type_checking_restores_validation(env: Environment, explicit: bool, exceptional: bool) -> None:
    target = Environment() if explicit else env
    mgr = target.formula_manager
    suspension = SuspendTypeChecking(target) if explicit else SuspendTypeChecking()
    with pytest.raises(RuntimeError) if exceptional else nullcontext():
        with suspension as selected:
            assert selected is target
            assert get_env() is env
            assert mgr.And(mgr.Int(1), mgr.TRUE()).is_and()
            if explicit:
                current_mgr = env.formula_manager
                with pytest.raises(PysmtTypeError):
                    current_mgr.And(current_mgr.Int(3), current_mgr.TRUE())
            if exceptional:
                raise RuntimeError("leave suspension")
    assert get_env() is env
    with pytest.raises(PysmtTypeError):
        mgr.And(mgr.Int(2), mgr.TRUE())
