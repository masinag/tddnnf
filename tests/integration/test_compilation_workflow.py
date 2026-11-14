from fractions import Fraction
from itertools import combinations, product

import pytest
from pysmt.typing import BOOL, INT, REAL, ArrayType, BVType
from tlemma_enum.solvers.mathsat_total import MathSATTotalEnumerator

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiledTarget, BddCompiler
from tddnnf.compilers.d4 import D4CompiledTarget, D4Compiler
from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler
from tddnnf.core.theory_compiled_target import TheoryCompiledTarget
from tddnnf.queries import BddEngine, DdnnifeEngine, SddEngine
from tests.integration.bank_cases import BANK_CASES

pytestmark = pytest.mark.integration

BACKENDS = [
    pytest.param(BddCompiler, BddCompiledTarget, BddEngine, id="bdd"),
    pytest.param(SddCompiler, SddCompiledTarget, SddEngine, id="sdd"),
    pytest.param(D4Compiler, D4CompiledTarget, DdnnifeEngine, id="d4"),
]


def workflow_cases(extended):
    cases = []
    for case in BANK_CASES:
        for backend in BACKENDS:
            compiler_type, target_type, engine_type = backend.values
            marks = []
            if compiler_type is D4Compiler and (
                (extended and case.name == "BV unsat") or (not extended and case.model_count == 0)
            ):
                marks = [pytest.mark.skip(reason="ddnnife cannot load the resulting constant d4 circuit")]
            cases.append(
                pytest.param(case, compiler_type, target_type, engine_type, id=f"{case.name}-{backend.id}", marks=marks)
            )
    return cases


@pytest.fixture
def symbols(env):
    env.enable_infix_notation = True
    mgr = env.formula_manager
    types = {
        **dict.fromkeys(("x", "y", "z"), REAL),
        **dict.fromkeys(("i", "j"), INT),
        **dict.fromkeys(("A", "B"), BOOL),
        **dict.fromkeys(("bv1", "bv2"), BVType(8)),
        **dict.fromkeys(("arr1", "arr2"), ArrayType(INT, INT)),
    }
    return {name: mgr.Symbol(name, typename) for name, typename in types.items()}


def literal_queries(mgr, atoms):
    yield []
    for width in (1, 2):
        for selected in combinations(atoms, width):
            for signs in product((True, False), repeat=width):
                yield [atom if positive else mgr.Not(atom) for atom, positive in zip(selected, signs)]


def satisfiable(env, formula):
    with env.factory.Solver(name="z3") as solver:
        solver.add_assertion(formula)
        return solver.solve()


def theory_models(env, formula, atoms):
    mgr = env.formula_manager
    models = set()
    with env.factory.Solver(name="z3") as solver:
        solver.add_assertion(formula)
        while solver.solve():
            values = tuple(solver.get_value(atom).is_true() for atom in atoms)
            models.add(values)
            solver.add_assertion(mgr.Or([mgr.Not(atom) if value else atom for atom, value in zip(atoms, values)]))
    return models


@pytest.mark.parametrize("case, compiler_type, target_type, engine_type", workflow_cases(extended=False))
def test_reduced_workflow(env, symbols, tmp_path, case, compiler_type, target_type, engine_type):
    mgr = env.formula_manager
    phi = case.formula_builder(symbols)
    with TheoryCompilation(phi, env=env) as compilation:
        atoms = compilation.atoms
        expected = theory_models(env, phi, atoms)
        assert len(expected) == case.model_count
        clauses = [mgr.Or(literals) for literals in literal_queries(mgr, atoms)]
        entailments = [not satisfiable(env, mgr.And(phi, mgr.Not(clause))) for clause in clauses]
        enumerator = MathSATTotalEnumerator()
        enumerator.check_all_sat(compilation.phi, atoms=list(atoms))
        target = compilation.compile_treduced(compiler_type(), enumerator.get_theory_lemmas())

    directory = tmp_path / "target"
    target.save(directory)
    loaded = TheoryCompiledTarget.load(directory, target_type, env=env)
    for container in (target, loaded):
        assert container.atoms == atoms
        with container.queries(engine_type) as session:
            assert session.is_satisfiable() == bool(expected)
            assert session.count_truth_assignments() == case.model_count
            assignments = list(session.enumerate_truth_assignments())
            for assignment in assignments:
                assert tuple(assignment) == atoms
                assert all(type(value) is bool for value in assignment.values())
            models = [tuple(assignment[atom] for atom in atoms) for assignment in assignments]
            assert len(models) == len(set(models))
            assert set(models) == expected
            for clause, entailed in zip(clauses, entailments):
                assert session.entails_clause(clause) == entailed, clause


@pytest.mark.parametrize("case, compiler_type, target_type, engine_type", workflow_cases(extended=True))
def test_extended_workflow(env, symbols, tmp_path, case, compiler_type, target_type, engine_type):
    mgr = env.formula_manager
    phi = case.formula_builder(symbols)
    with TheoryCompilation(phi, env=env) as compilation:
        atoms = compilation.atoms
        negated = mgr.Not(phi)
        expected = set(product((False, True), repeat=len(atoms))) - theory_models(env, negated, atoms)
        valid = not satisfiable(env, negated)
        cubes = [mgr.And(literals) for literals in literal_queries(mgr, atoms)]
        implicants = [not satisfiable(env, mgr.And(cube, negated)) for cube in cubes]
        enumerator = MathSATTotalEnumerator()
        enumerator.check_all_sat(mgr.Not(compilation.phi), atoms=list(atoms))
        lemmas = enumerator.get_theory_lemmas()
        lemmas_atoms = set().union(*(compilation.normalize(lemma).get_atoms() for lemma in lemmas))
        generated = lemmas_atoms - set(atoms)
        if compiler_type is D4Compiler and generated:
            with pytest.raises(NotImplementedError, match="universal.*elimination"):
                compilation.compile_textended(compiler_type(), lemmas)
            return
        target = compilation.compile_textended(compiler_type(), lemmas)

    directory = tmp_path / "target"
    target.save(directory)
    loaded = TheoryCompiledTarget.load(directory, target_type, env=env)
    for container in (target, loaded):
        assert container.atoms == atoms
        with container.queries(engine_type) as session:
            assert session.is_valid() == valid
            assert session.count_truth_assignments() == len(expected)
            assignments = list(session.enumerate_truth_assignments())
            for assignment in assignments:
                assert tuple(assignment) == atoms
                assert all(type(value) is bool for value in assignment.values())
            models = [tuple(assignment[atom] for atom in atoms) for assignment in assignments]
            assert len(models) == len(set(models))
            assert set(models) == expected
            for cube, implicant in zip(cubes, implicants):
                assert session.is_implicant(cube) == implicant, cube


@pytest.fixture(params=["dependent", "independent"])
def extra_atom_case(env, symbols, request):
    mgr = env.formula_manager
    x, y, z, a = (symbols[name] for name in ("x", "y", "z", "A"))
    phi = ((x + y >= 1) & a) | ((x + y <= 0) & ~a)
    kind = request.param
    extra = x + y <= mgr.Real(Fraction(1, 2)) if kind == "dependent" else z <= 0
    with TheoryCompilation(phi, env=env) as compilation:
        extra = compilation.normalize(extra)
        formula_atoms = tuple(sorted(compilation.phi.get_atoms(), key=lambda atom: atom.node_id()))
    assert extra not in formula_atoms
    return phi, (extra, *formula_atoms)


@pytest.mark.parametrize("compiler_type, target_type, engine_type", BACKENDS)
def test_reduced_extra_atom_workflow(env, tmp_path, extra_atom_case, compiler_type, target_type, engine_type):
    mgr = env.formula_manager
    phi, declared_atoms = extra_atom_case
    with TheoryCompilation(phi, atoms=declared_atoms, env=env) as compilation:
        atoms = compilation.atoms
        assert atoms == declared_atoms
        expected = theory_models(env, phi, atoms)
        clauses = [mgr.Or(literals) for literals in literal_queries(mgr, atoms)]
        entailments = [not satisfiable(env, mgr.And(phi, mgr.Not(clause))) for clause in clauses]
        enumerator = MathSATTotalEnumerator()
        enumerator.check_all_sat(compilation.phi, atoms=list(atoms))
        target = compilation.compile_treduced(compiler_type(), enumerator.get_theory_lemmas())

    directory = tmp_path / "target"
    target.save(directory)
    loaded = TheoryCompiledTarget.load(directory, target_type, env=env)
    for container in (target, loaded):
        assert container.atoms == declared_atoms
        with container.queries(engine_type) as session:
            assert session.is_satisfiable()
            assert session.count_truth_assignments() == len(expected)
            assignments = list(session.enumerate_truth_assignments())
            for assignment in assignments:
                assert tuple(assignment) == declared_atoms
                assert all(type(value) is bool for value in assignment.values())
            models = [tuple(assignment[atom] for atom in atoms) for assignment in assignments]
            assert len(models) == len(set(models))
            assert set(models) == expected
            for clause, entailed in zip(clauses, entailments):
                assert session.entails_clause(clause) == entailed, clause


@pytest.mark.parametrize("compiler_type, target_type, engine_type", BACKENDS)
def test_extended_extra_atom_workflow(env, tmp_path, extra_atom_case, compiler_type, target_type, engine_type):
    mgr = env.formula_manager
    phi, declared_atoms = extra_atom_case
    with TheoryCompilation(phi, atoms=declared_atoms, env=env) as compilation:
        atoms = compilation.atoms
        assert atoms == declared_atoms
        negated = mgr.Not(phi)
        expected = set(product((False, True), repeat=len(atoms))) - theory_models(env, negated, atoms)
        valid = not satisfiable(env, negated)
        cubes = [mgr.And(literals) for literals in literal_queries(mgr, atoms)]
        implicants = [not satisfiable(env, mgr.And(cube, negated)) for cube in cubes]
        enumerator = MathSATTotalEnumerator()
        enumerator.check_all_sat(mgr.Not(compilation.phi), atoms=list(atoms))
        target = compilation.compile_textended(compiler_type(), enumerator.get_theory_lemmas())

    directory = tmp_path / "target"
    target.save(directory)
    loaded = TheoryCompiledTarget.load(directory, target_type, env=env)
    for container in (target, loaded):
        assert container.atoms == declared_atoms
        with container.queries(engine_type) as session:
            assert session.is_valid() == valid
            assert session.count_truth_assignments() == len(expected)
            assignments = list(session.enumerate_truth_assignments())
            for assignment in assignments:
                assert tuple(assignment) == atoms
                assert all(type(value) is bool for value in assignment.values())
            models = [tuple(assignment[atom] for atom in atoms) for assignment in assignments]
            assert len(models) == len(set(models))
            assert set(models) == expected
            for cube, implicant in zip(cubes, implicants):
                assert session.is_implicant(cube) == implicant, cube
