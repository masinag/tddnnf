"""Full-bank exact direct-engine semantics and assumptions against solver models."""

from itertools import product

import pytest

from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.core.containers import TheoryCompiledTarget
from tests.queries.support import solver_models


def test_exhaustive_engine_and_solver_space(engine_factory, mgr, compiler, bank_case):
    target = compiler.compile(
        bank_case.original_formula,
        bank_case.abstr,
        all_atoms=bank_case.all_atoms,
        exists_atoms=bank_case.vars_to_forget,
    )
    if isinstance(target, D4CompiledTarget) and target.nnf_text in ("t 1\n", "f 1\n"):
        pytest.skip("ddnnife rejects constant circuits with zero native features; dedicated exception tests cover this")
    container = TheoryCompiledTarget(target, bank_case.abstr, bank_case.project_on, env=mgr.env)
    engine = engine_factory(container)
    expected = solver_models(mgr, bank_case.expected_formula, bank_case.project_on)
    models = list(engine.enumerate_truth_assignments())
    assert {frozenset(model.items()) for model in models} == expected
    assert len(models) == len(expected) == engine.count_truth_assignments()
    assert engine.is_satisfiable() == bool(expected)
    for values in product([True, False], repeat=len(bank_case.project_on)):
        model = dict(zip(bank_case.project_on, values))
        cube = [atom if value else mgr.Not(atom) for atom, value in model.items()]
        clause = [mgr.Not(atom) if value else atom for atom, value in model.items()]
        accepted = frozenset(model.items()) in expected
        assert engine.is_implicant(cube) == accepted
        assert engine.entails_clause(clause) == (not accepted)


def test_queries_with_assumptions(engine_factory, mgr, compiler, bank_case):
    target = compiler.compile(
        bank_case.original_formula,
        bank_case.abstr,
        all_atoms=bank_case.all_atoms,
        exists_atoms=bank_case.vars_to_forget,
    )
    if isinstance(target, D4CompiledTarget) and target.nnf_text in ("t 1\n", "f 1\n"):
        pytest.skip("ddnnife rejects constant circuits with zero native features; dedicated exception tests cover this")
    engine = engine_factory(TheoryCompiledTarget(target, bank_case.abstr, bank_case.project_on, env=mgr.env))
    atoms = bank_case.project_on
    valid_models = solver_models(mgr, bank_case.expected_formula, atoms)
    indices = {0, len(atoms) // 2, len(atoms) - 1} if atoms else set()
    assume_vars = [atoms[i] for i in sorted(indices)][:3]
    enumerated = {frozenset(model.items()) for model in engine.enumerate_truth_assignments()}
    for values in product([True, False], repeat=len(assume_vars)):
        assumption = frozenset(zip(assume_vars, values))
        literals = [atom if value else mgr.Not(atom) for atom, value in assumption]
        expected = {model for model in valid_models if assumption <= model}
        assert {model for model in enumerated if assumption <= model} == expected
        assert len(expected) == engine.count_truth_assignments(literals)
        assert engine.is_satisfiable(literals) == bool(expected)
