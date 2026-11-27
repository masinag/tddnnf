from collections.abc import Callable
from fractions import Fraction
from functools import partial
from itertools import combinations, product
from pathlib import Path
from typing import Iterator

import pytest
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.typing import BOOL, INT, REAL, ArrayType, BVType
from tlemma_enum.solvers.mathsat_total import MathSATTotalEnumerator

from tddnnf import TheoryCompilation
from tddnnf.compilation.compiler import PropCompiler
from tddnnf.compilation.cudd import CuddCompiledTarget, CuddCompiler
from tddnnf.compilation.d4 import D4CompiledTarget, D4Compiler
from tddnnf.compilation.pysdd import PySddCompiledTarget, PySddCompiler
from tddnnf.compilation.targets import PropCompiledTarget, TheoryCompiledTarget
from tddnnf.queries import CuddEngine, DdnnifeEngine, DecDnnfRsEngine, PySddEngine, QuerySession
from tddnnf.queries.engine import QueryEngine
from tests.helpers import satisfiable, theory_models
from tests.integration.bank_cases import BANK_CASES

pytestmark = pytest.mark.integration

D4_BACKENDS = [
    pytest.param(D4Compiler, D4CompiledTarget, DdnnifeEngine, id="d4-circuit-ddnnife"),
    pytest.param(
        partial(
            D4Compiler,
            input_mode="cnf",
            options=["--preproc", "compile-equiv", "--occurrence-manager", "dynamicPureSimp"],
        ),
        D4CompiledTarget,
        DdnnifeEngine,
        id="d4-cnf-ddnnife",
    ),
    pytest.param(D4Compiler, D4CompiledTarget, DecDnnfRsEngine, id="d4-circuit-decdnnf"),
]

BACKENDS = [
    pytest.param(CuddCompiler, CuddCompiledTarget, CuddEngine, id="cudd"),
    pytest.param(PySddCompiler, PySddCompiledTarget, PySddEngine, id="pysdd"),
    *D4_BACKENDS,
]


@pytest.mark.parametrize("compiler_factory, target_type, engine_type", BACKENDS)
@pytest.mark.parametrize("include_unused", [False, True], ids=["formula-atoms", "unused-retained-atom"])
@pytest.mark.parametrize(
    "eliminated_names, retained_names, expected_count",
    [
        pytest.param((), ("A", "B", "p", "q"), 5, id="eliminate-none"),
        pytest.param(("A",), ("B", "p", "q"), 4, id="eliminate-A"),
        pytest.param(("B",), ("A", "p", "q"), 4, id="eliminate-B"),
        pytest.param(("A", "B"), ("p", "q"), 3, id="eliminate-A-B"),
        pytest.param(("p", "q"), ("A", "B"), 3, id="eliminate-p-q"),
    ],
)
def test_reduced_projection_retains_only_declared_unquantified_atoms(
    env, compiler_factory, target_type, engine_type, include_unused, eliminated_names, retained_names, expected_count
):
    mgr = env.formula_manager
    x, y = (mgr.Symbol(name, REAL) for name in ("x", "y"))
    a, b = (mgr.Symbol(name) for name in ("A", "B"))
    p, q = mgr.LE(x, mgr.Real(0)), mgr.Equals(x, mgr.Real(1))
    r, s = mgr.LE(x, mgr.Real(1)), mgr.GE(x, mgr.Real(1))
    u = mgr.LE(y, mgr.Real(0))
    atoms = {"A": a, "B": b, "p": p, "q": q}
    declared = (a, b, p, q)
    retained = tuple(atoms[name] for name in retained_names)
    if include_unused:
        declared = (u, *declared)
        retained = (u, *retained)
        expected_count *= 2
    phi = mgr.And(mgr.Implies(a, p), mgr.Implies(b, q))
    lemmas = [
        mgr.Or(mgr.Not(p), mgr.Not(s)),
        mgr.Or(mgr.Not(p), r),
        mgr.Or(mgr.Not(q), r),
        mgr.Or(mgr.Not(q), s),
        mgr.Or(q, mgr.Not(r), mgr.Not(s)),
    ]
    with TheoryCompilation(phi, atoms=declared, env=env) as compilation:
        target = compilation.compile_treduced(
            compiler_factory(), lemmas, exists_atoms=[atoms[name] for name in eliminated_names]
        )

    assert target.atoms == retained
    expected = theory_models(env, phi, retained)
    assert len(expected) == expected_count
    with QuerySession(target, engine_type) as session:
        assert session.count_truth_assignments() == expected_count
        assignments = list(session.enumerate_truth_assignments())
        assert all(tuple(assignment) == retained for assignment in assignments)
        models = [tuple(assignment[atom] for atom in retained) for assignment in assignments]
        assert len(models) == len(set(models))
        assert set(models) == expected


def workflow_cases(extended: bool) -> list:
    cases = []
    for case in BANK_CASES:
        formula_factory, model_count = case.values
        for backend in BACKENDS:
            compiler_factory, target_type, engine_type = backend.values
            marks = []
            if target_type is D4CompiledTarget and (
                (extended and case.id == "BV unsat") or (not extended and model_count == 0)
            ):
                marks = [pytest.mark.skip(reason="ddnnife cannot load the resulting constant d4 circuit")]
            cases.append(
                pytest.param(
                    formula_factory,
                    model_count,
                    compiler_factory,
                    target_type,
                    engine_type,
                    id=f"{case.id}-{backend.id}",
                    marks=marks,
                )
            )
    return cases


@pytest.fixture
def symbols(env: Environment) -> dict[str, FNode]:
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


def literal_queries(mgr: FormulaManager, atoms: tuple[FNode, ...]) -> Iterator[list[FNode]]:
    yield []
    for width in (1, 2):
        for selected in combinations(atoms, width):
            for signs in product((True, False), repeat=width):
                yield [atom if positive else mgr.Not(atom) for atom, positive in zip(selected, signs)]


@pytest.mark.parametrize(
    "formula_factory, model_count, compiler_factory, target_type, engine_type", workflow_cases(extended=False)
)
def test_reduced_workflow(
    env: Environment,
    symbols: dict[str, FNode],
    tmp_path: Path,
    formula_factory: Callable[[dict[str, FNode]], FNode],
    model_count: int,
    compiler_factory: Callable[[], PropCompiler],
    target_type: type[PropCompiledTarget],
    engine_type: type[QueryEngine],
):
    mgr = env.formula_manager
    phi = formula_factory(symbols)
    with TheoryCompilation(phi, env=env) as compilation:
        atoms = compilation.atoms
        expected = theory_models(env, phi, atoms)
        assert len(expected) == model_count
        clauses = [mgr.Or(literals) for literals in literal_queries(mgr, atoms)]
        entailments = [not satisfiable(env, mgr.And(phi, mgr.Not(clause))) for clause in clauses]
        enumerator = MathSATTotalEnumerator()
        enumerator.check_all_sat(compilation.phi, atoms=list(atoms))
        target = compilation.compile_treduced(compiler_factory(), enumerator.get_theory_lemmas())

    directory = tmp_path / "target"
    target.save(directory)
    loaded = TheoryCompiledTarget.load(directory, target_type, env=env)
    for container in (target, loaded):
        assert container.atoms == atoms
        with QuerySession(container, engine_type) as session:
            assert session.is_satisfiable() == bool(expected)
            assert session.count_truth_assignments() == model_count
            assignments = list(session.enumerate_truth_assignments())
            for assignment in assignments:
                assert tuple(assignment) == atoms
                assert all(type(value) is bool for value in assignment.values())
            models = [tuple(assignment[atom] for atom in atoms) for assignment in assignments]
            assert len(models) == len(set(models))
            assert set(models) == expected
            for clause, entailed in zip(clauses, entailments):
                assert session.entails_clause(clause) == entailed, clause


@pytest.mark.parametrize(
    "formula_factory, model_count, compiler_factory, target_type, engine_type", workflow_cases(extended=True)
)
def test_extended_workflow(
    env: Environment,
    symbols: dict[str, FNode],
    tmp_path: Path,
    formula_factory: Callable[[dict[str, FNode]], FNode],
    model_count: int,
    compiler_factory: Callable[[], PropCompiler],
    target_type: type[PropCompiledTarget],
    engine_type: type[QueryEngine],
):
    mgr = env.formula_manager
    phi = formula_factory(symbols)
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
        if target_type is D4CompiledTarget and generated:
            with pytest.raises(NotImplementedError, match="universal.*elimination"):
                compilation.compile_textended(compiler_factory(), lemmas)
            return
        target = compilation.compile_textended(compiler_factory(), lemmas)

    directory = tmp_path / "target"
    target.save(directory)
    loaded = TheoryCompiledTarget.load(directory, target_type, env=env)
    for container in (target, loaded):
        assert container.atoms == atoms
        with QuerySession(container, engine_type) as session:
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


@pytest.mark.parametrize("compiler_factory, target_type, engine_type", BACKENDS)
def test_reduced_extra_atom_workflow(
    env: Environment,
    tmp_path: Path,
    extra_atom_case: tuple[FNode, tuple[FNode, ...]],
    compiler_factory: Callable[[], PropCompiler],
    target_type: type[PropCompiledTarget],
    engine_type: type[QueryEngine],
):
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
        target = compilation.compile_treduced(compiler_factory(), enumerator.get_theory_lemmas())

    directory = tmp_path / "target"
    target.save(directory)
    loaded = TheoryCompiledTarget.load(directory, target_type, env=env)
    for container in (target, loaded):
        assert container.atoms == declared_atoms
        with QuerySession(container, engine_type) as session:
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


@pytest.mark.parametrize("compiler_factory, target_type, engine_type", BACKENDS)
def test_extended_extra_atom_workflow(
    env: Environment,
    tmp_path: Path,
    extra_atom_case: tuple[FNode, tuple[FNode, ...]],
    compiler_factory: Callable[[], PropCompiler],
    target_type: type[PropCompiledTarget],
    engine_type: type[QueryEngine],
):
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
        target = compilation.compile_textended(compiler_factory(), enumerator.get_theory_lemmas())

    directory = tmp_path / "target"
    target.save(directory)
    loaded = TheoryCompiledTarget.load(directory, target_type, env=env)
    for container in (target, loaded):
        assert container.atoms == declared_atoms
        with QuerySession(container, engine_type) as session:
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
