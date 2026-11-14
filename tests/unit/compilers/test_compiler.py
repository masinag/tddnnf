import pytest
from pysmt.shortcuts import FALSE, TRUE, And, Not, Or, Symbol

from tddnnf.compilers.cudd import BddCompiledTarget, BddCompiler
from tddnnf.compilers.d4 import D4CompiledTarget, D4Compiler
from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler
from tddnnf.core.abstraction import Abstractor
from tests.cases import ELIMINATION_CASES, PLAIN_CASES


def assert_equivalent(env, reconstructed, expected):
    mgr = env.formula_manager
    with env.factory.Solver(name="z3") as solver:
        solver.add_assertion(mgr.Not(mgr.Iff(reconstructed, expected)))
        assert not solver.solve()


@pytest.mark.parametrize("compiler_type", [BddCompiler, SddCompiler, D4Compiler], ids=["bdd", "sdd", "d4"])
@pytest.mark.parametrize("formula_factory", PLAIN_CASES)
def test_plain_compilation_preserves_meaning(env, compiler_type, formula_factory):
    formula = formula_factory()
    atoms = sorted(formula.get_atoms(), key=lambda atom: atom.symbol_name())
    abstractor = Abstractor()
    for atom in atoms:
        abstractor.get_id(atom)

    target = compiler_type().compile(formula, abstractor, all_atoms=atoms)

    assert_equivalent(env, target.to_pysmt(abstractor, env.formula_manager), formula)


@pytest.mark.parametrize("compiler_type", [BddCompiler, SddCompiler, D4Compiler], ids=["bdd", "sdd", "d4"])
@pytest.mark.parametrize("formula_factory, variable_names", ELIMINATION_CASES)
def test_existential_elimination(env, compiler_type, formula_factory, variable_names):
    formula = formula_factory()
    atoms = sorted(formula.get_atoms(), key=lambda atom: atom.symbol_name())
    variables = [Symbol(name) for name in variable_names]
    abstractor = Abstractor()
    for atom in atoms:
        abstractor.get_id(atom)

    target = compiler_type().compile(formula, abstractor, all_atoms=atoms, exists_atoms=variables)
    reconstructed = target.to_pysmt(abstractor, env.formula_manager)

    assert set(variables).isdisjoint(reconstructed.get_atoms())
    assert_equivalent(env, reconstructed, env.formula_manager.Exists(variables, formula))


@pytest.mark.parametrize("compiler_type", [BddCompiler, SddCompiler], ids=["bdd", "sdd"])
@pytest.mark.parametrize("formula_factory, variable_names", ELIMINATION_CASES)
def test_universal_elimination(env, compiler_type, formula_factory, variable_names):
    formula = formula_factory()
    atoms = sorted(formula.get_atoms(), key=lambda atom: atom.symbol_name())
    variables = [Symbol(name) for name in variable_names]
    abstractor = Abstractor()
    for atom in atoms:
        abstractor.get_id(atom)

    target = compiler_type().compile(formula, abstractor, all_atoms=atoms, forall_atoms=variables)
    reconstructed = target.to_pysmt(abstractor, env.formula_manager)

    assert set(variables).isdisjoint(reconstructed.get_atoms())
    assert_equivalent(env, reconstructed, env.formula_manager.ForAll(variables, formula))


def test_d4_rejects_universal_elimination(env):
    p, q = (Symbol(name) for name in ("p", "q"))
    abstractor = Abstractor()
    for atom in (p, q):
        abstractor.get_id(atom)

    with pytest.raises(NotImplementedError):
        D4Compiler().compile(And(p, q), abstractor, all_atoms=[p, q], forall_atoms=[q])


@pytest.mark.parametrize(
    "compiler_type, target_type",
    [(BddCompiler, BddCompiledTarget), (SddCompiler, SddCompiledTarget), (D4Compiler, D4CompiledTarget)],
    ids=["bdd", "sdd", "d4"],
)
@pytest.mark.parametrize(
    "formula_factory",
    [
        pytest.param(TRUE, id="true"),
        pytest.param(FALSE, id="false"),
        pytest.param(lambda: And(Symbol("p"), Or(Not(Symbol("q")), Symbol("r"))), id="compound"),
    ],
)
def test_native_round_trip_preserves_meaning(env, tmp_path, compiler_type, target_type, formula_factory):
    formula = formula_factory()
    atoms = sorted(formula.get_atoms(), key=lambda atom: atom.symbol_name())
    abstractor = Abstractor({7 * index: atom for index, atom in enumerate(atoms, 1)})
    target = compiler_type().compile(formula, abstractor, all_atoms=atoms)

    directory = tmp_path / "target"
    target.save(directory)
    loaded = target_type.load(directory)
    mgr = env.formula_manager
    reconstructed = loaded.to_pysmt(abstractor, mgr)

    with env.factory.Solver(name="z3") as solver:
        solver.add_assertion(mgr.Not(mgr.Iff(reconstructed, formula)))
        assert not solver.solve()
