from typing import Iterator

import pytest
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import FALSE, TRUE, And, Not, Or, Symbol

from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import QueryEngine
from tddnnf.core.theory_compiled_target import TheoryCompiledTarget
from tddnnf.queries.bdd_engine import BddEngine
from tddnnf.queries.ddnnife_engine import DdnnifeEngine
from tddnnf.queries.sdd_engine import SddEngine
from tests.helpers import satisfiable, theory_models
from tests.unit.cases import ELIMINATION_CASES, PLAIN_CASES

# ddnnife cannot load d4's constant circuits.
DDNNIFE_PLAIN_CASES = [case for case in PLAIN_CASES if case.values[0] not in (TRUE, FALSE)]
ENGINE_GROUPS = [
    ("bdd", BddCompiler, BddEngine, PLAIN_CASES, None),
    ("bdd", BddCompiler, BddEngine, ELIMINATION_CASES, "exists"),
    ("bdd", BddCompiler, BddEngine, ELIMINATION_CASES, "forall"),
    ("sdd", SddCompiler, SddEngine, PLAIN_CASES, None),
    ("sdd", SddCompiler, SddEngine, ELIMINATION_CASES, "exists"),
    ("sdd", SddCompiler, SddEngine, ELIMINATION_CASES, "forall"),
    ("d4", D4Compiler, DdnnifeEngine, DDNNIFE_PLAIN_CASES, None),
    ("d4", D4Compiler, DdnnifeEngine, ELIMINATION_CASES, "exists"),
]
LITERAL_QUERY_KINDS = ("empty", "positive", "negative", "contradictory", "all-positive", "all-negative", "mixed")
ENGINE_CASES = []
QUERY_CASES = []
ASSUMPTION_CASES = []
for backend, compiler_type, engine_type, formula_cases, quantifier in ENGINE_GROUPS:
    for case in formula_cases:
        factory, names = case.values if quantifier else (case.values[0], ())
        compiled_input = (compiler_type, engine_type, factory, names, quantifier)
        case_id = f"{backend}-{quantifier}-{case.id}" if quantifier else f"{backend}-{case.id}"
        ENGINE_CASES.append(pytest.param(compiled_input, id=case_id))
        query_kinds = ("empty",) if factory in (TRUE, FALSE) else LITERAL_QUERY_KINDS
        for kind in query_kinds:
            query_case = pytest.param(compiled_input, kind, id=f"{case_id}-{kind}")
            QUERY_CASES.append(query_case)
            ASSUMPTION_CASES.append(query_case)
        ASSUMPTION_CASES.append(pytest.param(compiled_input, "default", id=f"{case_id}-default"))


CompiledCaseType = tuple[QueryEngine, FNode, tuple[FNode, ...]]


@pytest.fixture
def compiled_case(env: Environment, request: pytest.FixtureRequest) -> Iterator[CompiledCaseType]:
    compiler_type, engine_type, factory, names, quantifier = request.param
    formula = factory()
    atoms = sorted(formula.get_atoms(), key=lambda atom: atom.symbol_name())
    variables = [Symbol(name) for name in names]
    abstractor = Abstractor()
    for atom in atoms:
        abstractor.get_id(atom)
    arguments = {f"{quantifier}_atoms": variables} if quantifier else {}
    target = compiler_type().compile(formula, abstractor, all_atoms=atoms, **arguments)
    retained = tuple(atom for atom in atoms if atom not in variables)
    container = TheoryCompiledTarget(target, abstractor, retained, env=env)
    expected = formula
    if quantifier == "exists":
        expected = env.formula_manager.Exists(variables, formula)
    elif quantifier == "forall":
        expected = env.formula_manager.ForAll(variables, formula)
    engine = engine_type(container)
    try:
        yield engine, expected, retained
    finally:
        engine.close()


def query_literals(kind: str, atoms: tuple[FNode, ...]) -> list[FNode] | None:
    if kind == "default":
        return None
    if kind == "empty":
        return []
    if kind == "positive":
        return [atoms[0]]
    if kind == "negative":
        return [Not(atoms[0])]
    if kind == "contradictory":
        return [atoms[0], Not(atoms[0])]
    if kind == "all-positive":
        return list(atoms)
    if kind == "all-negative":
        return [Not(atom) for atom in atoms]
    assert kind == "mixed"
    return [atom if index % 2 == 0 else Not(atom) for index, atom in enumerate(atoms)]


@pytest.mark.parametrize("compiled_case, query_kind", ASSUMPTION_CASES, indirect=["compiled_case"])
def test_satisfiability(env: Environment, compiled_case: CompiledCaseType, query_kind: str):
    engine, formula, atoms = compiled_case
    assumptions = query_literals(query_kind, atoms)
    expected = satisfiable(env, And(formula, And(assumptions or [])))
    actual = engine.is_satisfiable() if assumptions is None else engine.is_satisfiable(assumptions)
    assert actual == expected


@pytest.mark.parametrize("compiled_case", ENGINE_CASES, indirect=True)
def test_validity(env: Environment, compiled_case: CompiledCaseType):
    engine, formula, _ = compiled_case
    assert engine.is_valid() == (not satisfiable(env, Not(formula)))


@pytest.mark.parametrize("compiled_case, query_kind", ASSUMPTION_CASES, indirect=["compiled_case"])
def test_counting(env: Environment, compiled_case: CompiledCaseType, query_kind: str):
    engine, formula, atoms = compiled_case
    assumptions = query_literals(query_kind, atoms)
    expected = theory_models(env, And(formula, And(assumptions or [])), atoms)
    actual = engine.count_truth_assignments() if assumptions is None else engine.count_truth_assignments(assumptions)
    assert actual == len(expected)


@pytest.mark.parametrize("compiled_case, query_kind", QUERY_CASES, indirect=["compiled_case"])
def test_clause_entailment(env: Environment, compiled_case: CompiledCaseType, query_kind: str):
    engine, formula, atoms = compiled_case
    clause = query_literals(query_kind, atoms)
    assert clause is not None
    assert engine.entails_clause(clause) == (not satisfiable(env, And(formula, Not(Or(clause)))))


@pytest.mark.parametrize("compiled_case, query_kind", QUERY_CASES, indirect=["compiled_case"])
def test_implicants(env: Environment, compiled_case: CompiledCaseType, query_kind: str):
    engine, formula, atoms = compiled_case
    cube = query_literals(query_kind, atoms)
    assert cube is not None
    assert engine.is_implicant(cube) == (not satisfiable(env, And(And(cube), Not(formula))))


@pytest.mark.parametrize("compiled_case", ENGINE_CASES, indirect=True)
def test_enumeration(env: Environment, compiled_case: CompiledCaseType):
    engine, formula, atoms = compiled_case
    assignments = list(engine.enumerate_truth_assignments())
    for assignment in assignments:
        assert tuple(assignment) == atoms
        assert all(type(value) is bool for value in assignment.values())
    models = [tuple(assignment[atom] for atom in atoms) for assignment in assignments]
    expected = theory_models(env, formula, atoms)
    assert len(models) == len(set(models))
    assert set(models) == expected
    assert len(models) == engine.count_truth_assignments() == len(expected)
