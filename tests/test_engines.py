import itertools

import ddnnife
import pytest
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4CompiledTarget, D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import PropCompiler, QueryEngine
from tddnnf.queries import BddEngine, DdnnifeEngine, SddEngine
from tddnnf.queries.session import QuerySession
from tests.conftest import SolverGroundTruth

PAIRINGS = [(BddCompiler, BddEngine), (SddCompiler, SddEngine), (D4Compiler, DdnnifeEngine)]


@pytest.fixture(params=PAIRINGS, ids=["bdd", "sdd", "ddnnife"])
def pairing(request):
    return request.param


@pytest.fixture
def compiler(pairing):
    return pairing[0]()


@pytest.fixture(params=[False, True], ids=["engine", "session"])
def engine_factory(pairing, request):
    opened = []

    def create(target):
        engine = target.queries(pairing[1]) if request.param else pairing[1](target)
        opened.append(engine)
        return engine

    yield create
    for engine in reversed(opened):
        engine.close()


def query_literals(engine, mgr, operation, literals):
    query = literals
    if isinstance(engine, QuerySession):
        query = mgr.Or(literals) if operation == "entails_clause" else mgr.And(literals)
    return getattr(engine, operation)(query)


@pytest.fixture
def engine(
    compiler: PropCompiler, abstr: Abstractor, mgr: FormulaManager, a: FNode, b: FNode, engine_factory
) -> QueryEngine:
    abstr = Abstractor({1: a, 2: b})
    target = compiler.compile(mgr.And(a, b), abstr)
    return engine_factory(TheoryCompiledTarget(target, abstr, projection_atoms=[a, b], env=mgr.env))


def test_exhaustive_engine_and_solver_space(
    mgr: FormulaManager, compiler: PropCompiler, abstr: Abstractor, bank_case: SolverGroundTruth, engine_factory
) -> None:
    abstr = bank_case.abstr
    target = compiler.compile(bank_case.original_formula, abstr, project_on=bank_case.project_on)
    container = TheoryCompiledTarget(target, abstr, projection_atoms=bank_case.project_on, env=mgr.env)
    if isinstance(target, D4CompiledTarget) and target.nnf_text in ("t 1\n", "f 1\n"):
        with pytest.raises(ddnnife.InternalError):
            engine_factory(container)
        return
    engine = engine_factory(container)

    with mgr.env.factory.Solver() as solver:
        solver.add_assertion(bank_case.expected_formula)
        solver_has_models = solver.solve()
    assert engine.is_satisfiable() == solver_has_models

    engine_pos_list = list(engine.enumerate_truth_assignments())
    assert len(engine_pos_list) == engine.count_truth_assignments()

    engine_pos_set = {frozenset(asg.items()) for asg in engine_pos_list}

    projected_vars = bank_case.project_on
    all_combinations = itertools.product([True, False], repeat=len(projected_vars))

    all_pos_conjunctions = []
    all_neg_conjunctions = []

    for combo in all_combinations:
        asg = dict(zip(projected_vars, combo))
        asg_frozen = frozenset(asg.items())

        cube = [v if val else mgr.Not(v) for v, val in asg.items()]
        conj = mgr.And(cube)

        if asg_frozen in engine_pos_set:
            all_pos_conjunctions.append(conj)

            assert query_literals(engine, mgr, "is_implicant", cube)

            with mgr.env.factory.Solver() as solver:
                solver.add_assertion(mgr.And(conj, mgr.Not(bank_case.expected_formula)))
                assert not solver.solve(), f"Engine model {asg} is logically rejected by the SMT solver!"
        else:
            all_neg_conjunctions.append(conj)

            assert not query_literals(engine, mgr, "is_implicant", cube)

            with mgr.env.factory.Solver() as solver:
                solver.add_assertion(mgr.And(conj, bank_case.expected_formula))
                assert not solver.solve(), f"Engine missed a valid solver assignment: {asg}"

            clause = [mgr.Not(v) if val else v for v, val in asg.items()]
            entailed_clause = mgr.Or(clause)
            assert query_literals(engine, mgr, "entails_clause", clause)

            with mgr.env.factory.Solver() as solver:
                solver.add_assertion(mgr.And(bank_case.expected_formula, mgr.Not(entailed_clause)))
                assert not solver.solve()

    pos_disjunction = mgr.Or(*all_pos_conjunctions) if all_pos_conjunctions else mgr.FALSE()
    with mgr.env.factory.Solver() as solver:
        solver.add_assertion(mgr.And(bank_case.expected_formula, mgr.Not(pos_disjunction)))
        assert not solver.solve(), "Engine positive model enumeration failed completeness proof!"

    neg_disjunction = mgr.Or(*all_neg_conjunctions) if all_neg_conjunctions else mgr.FALSE()
    with mgr.env.factory.Solver() as solver:
        solver.add_assertion(mgr.And(mgr.Not(bank_case.expected_formula), mgr.Not(neg_disjunction)))
        assert not solver.solve(), "Engine counter-model state coverage is incomplete!"


@pytest.mark.parametrize("reverse", [False, True])
def test_enumeration_projection_order(mgr, compiler, a, b, reverse, engine_factory):
    projection = [b, a] if reverse else [a, b]
    abstr = Abstractor({1: a, 2: b})
    native = compiler.compile(mgr.Or(a, b), abstr, project_on=projection)
    engine = engine_factory(TheoryCompiledTarget(native, abstr, projection, env=mgr.env))
    try:
        models = list(engine.enumerate_truth_assignments())
        assert len(models) == 3
        assert all(tuple(model) == tuple(projection) for model in models)
    finally:
        engine.close()


def test_queries_with_assumptions(
    mgr: FormulaManager, compiler: PropCompiler, abstr: Abstractor, bank_case: SolverGroundTruth, engine_factory
) -> None:
    abstr = bank_case.abstr
    target = compiler.compile(bank_case.original_formula, abstr, project_on=bank_case.project_on)
    container = TheoryCompiledTarget(target, abstr, projection_atoms=bank_case.project_on, env=mgr.env)
    if isinstance(target, D4CompiledTarget) and target.nnf_text in ("t 1\n", "f 1\n"):
        with pytest.raises(ddnnife.InternalError):
            engine_factory(container)
        return
    engine = engine_factory(container)

    projected_vars = bank_case.project_on
    if not projected_vars:
        return

    valid_models = []
    all_combinations = itertools.product([True, False], repeat=len(projected_vars))
    for combo in all_combinations:
        asg = dict(zip(projected_vars, combo))
        conj = mgr.And([v if val else mgr.Not(v) for v, val in asg.items()])

        with mgr.env.factory.Solver() as solver:
            solver.add_assertion(mgr.And(conj, bank_case.expected_formula))
            if solver.solve():
                valid_models.append(asg)

    #  Pick a small subset of the projected variables to act as our assumptions
    indices = {0, len(projected_vars) // 2, len(projected_vars) - 1}
    assume_vars = [projected_vars[i] for i in sorted(indices)][:3]
    assume_combinations = itertools.product([True, False], repeat=len(assume_vars))

    for assume_combo in assume_combinations:
        assume_dict = dict(zip(assume_vars, assume_combo))
        assumptions = [v if val else mgr.Not(v) for v, val in assume_dict.items()]

        expected_count = 0
        for model in valid_models:
            if all(model[v] == assume_dict[v] for v in assume_vars):
                expected_count += 1

        expected_sat = expected_count > 0

        assert engine.is_satisfiable(assumptions=assumptions) == expected_sat, (
            f"Engine sat under assumptions {assume_dict} failed."
        )

        assert engine.count_truth_assignments(assumptions=assumptions) == expected_count, (
            f"Engine model count under assumptions {assume_dict} failed."
        )


@pytest.mark.parametrize(
    ("polarities", "expected_count"),
    [(None, 3), ([], 3), ([True, True], 2), ([True, False], 0), ([False], 1)],
    ids=["none", "empty", "duplicate", "contradictory", "negative"],
)
def test_normalized_assumptions(
    mgr: FormulaManager,
    compiler: PropCompiler,
    a: FNode,
    b: FNode,
    polarities: list[bool] | None,
    expected_count: int,
    engine_factory,
) -> None:
    abstr = Abstractor({1: a, 2: b})
    target = compiler.compile(mgr.Or(a, b), abstr)
    engine = engine_factory(TheoryCompiledTarget(target, abstr, projection_atoms=[a, b], env=mgr.env))
    assumptions = None if polarities is None else [a if positive else mgr.Not(a) for positive in polarities]
    assert engine.is_satisfiable(assumptions) == (expected_count > 0)
    assert engine.count_truth_assignments(assumptions) == expected_count


def test_flat_literal_semantics(engine, mgr, a, b, engine_factory):
    for literals, entailed, implicant, count in (
        ([], False, False, 1),
        ([mgr.TRUE()], True, False, 1),
        ([mgr.FALSE()], False, True, 0),
        ([mgr.Not(mgr.TRUE())], False, True, 0),
        ([mgr.Not(mgr.FALSE())], True, False, 1),
        ([a, a], True, False, 1),
        ([a, mgr.Not(a)], True, True, 0),
        ([a, b], True, True, 1),
        ([mgr.FALSE(), a], True, True, 0),
        ([mgr.TRUE(), mgr.Not(a)], True, False, 0),
    ):
        assert query_literals(engine, mgr, "entails_clause", literals) == entailed
        assert query_literals(engine, mgr, "is_implicant", literals) == implicant
        assert engine.is_satisfiable(literals) == (count > 0)
        assert engine.count_truth_assignments(literals) == count


def test_validates_before_shortcuts(engine, mgr, a, b, c, engine_factory):
    for tail in (c, mgr.Iff(a, b)):
        for prefix in ([mgr.TRUE()], [mgr.FALSE()], [a, mgr.Not(a)]):
            literals = [*prefix, tail]
            for operation in ("entails_clause", "is_implicant"):
                with pytest.raises(ValueError):
                    query_literals(engine, mgr, operation, literals)
            for operation in (engine.is_satisfiable, engine.count_truth_assignments):
                with pytest.raises(ValueError):
                    operation(literals)


# --- Error / Validation Tests ---


def test_is_satisfiable_unknown_assumption(engine: QueryEngine, c: FNode, engine_factory) -> None:
    with pytest.raises(ValueError, match="not .*projection"):
        engine.is_satisfiable(assumptions=[c])


def test_count_truth_assignments_unknown_assumption(engine: QueryEngine, c: FNode, engine_factory) -> None:
    with pytest.raises(ValueError, match="not .*projection"):
        engine.count_truth_assignments(assumptions=[c])


def test_entails_clause_unknown_atom(engine: QueryEngine, c: FNode, mgr: FormulaManager, engine_factory) -> None:
    with pytest.raises(ValueError, match="not .*projection"):
        query_literals(engine, mgr, "entails_clause", [c])


def test_is_implicant_unknown_atom(engine: QueryEngine, c: FNode, mgr: FormulaManager, engine_factory) -> None:
    with pytest.raises(ValueError, match="not .*projection"):
        query_literals(engine, mgr, "is_implicant", [c])


def test_is_implicant_invalid_input(
    engine: QueryEngine, mgr: FormulaManager, a: FNode, b: FNode, engine_factory
) -> None:
    with pytest.raises(ValueError):
        query_literals(engine, mgr, "is_implicant", [mgr.Or(a, b)])


def test_projected_assumption_on_forgotten_var_raises(
    mgr: FormulaManager, compiler: PropCompiler, abstr: Abstractor, a: FNode, b: FNode, c: FNode, engine_factory
) -> None:
    abstr = Abstractor({1: a, 2: b, 3: c})
    target = compiler.compile(mgr.And(a, mgr.Or(b, c)), abstr, project_on=[a, b])
    engine = engine_factory(TheoryCompiledTarget(target, abstr, projection_atoms=[a, b], env=mgr.env))
    with pytest.raises(ValueError, match="not .*projection"):
        engine.is_satisfiable(assumptions=[c])
    with pytest.raises(ValueError, match="not .*projection"):
        engine.count_truth_assignments(assumptions=[c])
