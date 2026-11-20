from functools import partial
from pathlib import Path
from typing import Callable

import pytest
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.shortcuts import FALSE, TRUE, And, Not, Or, Symbol

from tddnnf.compilation.compiler import PropCompiler
from tddnnf.compilation.cudd import CuddCompiledTarget, CuddCompiler
from tddnnf.compilation.d4 import D4CompiledTarget, D4Compiler
from tddnnf.compilation.pysdd import PySddCompiledTarget, PySddCompiler
from tddnnf.compilation.targets import PropCompiledTarget
from tddnnf.core.abstraction import Abstractor
from tests.helpers import equivalent
from tests.unit.cases import ELIMINATION_CASES, PLAIN_CASES

FormulaFactoryType = Callable[[], FNode]
COMPILERS = [CuddCompiler, PySddCompiler, D4Compiler, partial(D4Compiler, input_mode="cnf")]
COMPILER_IDS = ["cudd", "pysdd", "d4", "d4-cnf"]


@pytest.mark.parametrize("compiler_type", COMPILERS, ids=COMPILER_IDS)
@pytest.mark.parametrize("formula_factory", PLAIN_CASES)
def test_plain_compilation_preserves_meaning(
    env: Environment, compiler_type: Callable[[], PropCompiler], formula_factory: FormulaFactoryType
):
    formula = formula_factory()
    atoms = sorted(formula.get_atoms(), key=lambda atom: atom.symbol_name())
    abstractor = Abstractor()
    for atom in atoms:
        abstractor.get_id(atom)

    target = compiler_type().compile(formula, abstractor, all_atoms=atoms)

    assert equivalent(env, target.to_pysmt(abstractor, env.formula_manager), formula)


@pytest.mark.parametrize("compiler_type", COMPILERS, ids=COMPILER_IDS)
@pytest.mark.parametrize(
    "formula_factory, variable_names",
    [
        *ELIMINATION_CASES,
        pytest.param(lambda: Symbol("p"), ("p",), id="atom"),
        pytest.param(lambda: And(Symbol("p"), Not(Symbol("p"))), ("p",), id="contradiction"),
        pytest.param(lambda: Or(Symbol("p"), Not(Symbol("p"))), ("p",), id="tautology"),
    ],
)
def test_existential_elimination(
    env: Environment,
    compiler_type: Callable[[], PropCompiler],
    formula_factory: FormulaFactoryType,
    variable_names: list[str],
):
    formula = formula_factory()
    atoms = sorted(formula.get_atoms(), key=lambda atom: atom.symbol_name())
    variables = [Symbol(name) for name in variable_names]
    abstractor = Abstractor()
    for atom in atoms:
        abstractor.get_id(atom)

    target = compiler_type().compile(formula, abstractor, all_atoms=atoms, exists_atoms=variables)
    reconstructed = target.to_pysmt(abstractor, env.formula_manager)

    assert set(variables).isdisjoint(reconstructed.get_atoms())
    assert equivalent(env, reconstructed, env.formula_manager.Exists(variables, formula))


@pytest.mark.parametrize("compiler_type", COMPILERS, ids=COMPILER_IDS)
@pytest.mark.parametrize(
    "formula_factory, atom_names",
    [
        pytest.param(TRUE, ["p"], id="true-with-declared-atom"),
        pytest.param(FALSE, ["p"], id="false-with-declared-atom"),
        pytest.param(lambda: Symbol("p"), ["p", "q"], id="unused-declared-atom"),
        pytest.param(
            lambda: Or(*(And(Symbol(f"p{i}"), Symbol(f"p{i + 1}")) for i in range(0, 10, 2))),
            [f"p{i}" for i in range(11)],
            id="auxiliaries-with-unused-declared-atom",
        ),
    ],
)
def test_compilation_preserves_meaning_and_declared_abstraction(
    env: Environment,
    compiler_type: Callable[[], PropCompiler],
    formula_factory: FormulaFactoryType,
    atom_names: list[str],
):
    formula = formula_factory()
    atoms = [Symbol(name) for name in atom_names]
    abstraction = {7 * index: atom for index, atom in enumerate(atoms, 1)}
    abstractor = Abstractor(abstraction)

    target = compiler_type().compile(formula, abstractor, all_atoms=atoms)
    reconstructed = target.to_pysmt(abstractor, env.formula_manager)

    assert equivalent(env, reconstructed, formula)
    assert dict(abstractor.id_to_atom) == abstraction
    assert dict(abstractor.atom_to_id) == {atom: idx for idx, atom in abstraction.items()}


@pytest.mark.parametrize("compiler_type", [CuddCompiler, PySddCompiler], ids=["cudd", "pysdd"])
@pytest.mark.parametrize("formula_factory, variable_names", ELIMINATION_CASES)
def test_universal_elimination(
    env: Environment,
    compiler_type: Callable[[], PropCompiler],
    formula_factory: FormulaFactoryType,
    variable_names: list[str],
):
    formula = formula_factory()
    atoms = sorted(formula.get_atoms(), key=lambda atom: atom.symbol_name())
    variables = [Symbol(name) for name in variable_names]
    abstractor = Abstractor()
    for atom in atoms:
        abstractor.get_id(atom)

    target = compiler_type().compile(formula, abstractor, all_atoms=atoms, forall_atoms=variables)
    reconstructed = target.to_pysmt(abstractor, env.formula_manager)

    assert set(variables).isdisjoint(reconstructed.get_atoms())
    assert equivalent(env, reconstructed, env.formula_manager.ForAll(variables, formula))


@pytest.mark.parametrize(
    "compiler_type, target_type",
    [
        (CuddCompiler, CuddCompiledTarget),
        (PySddCompiler, PySddCompiledTarget),
        (D4Compiler, D4CompiledTarget),
        (partial(D4Compiler, input_mode="cnf"), D4CompiledTarget),
    ],
    ids=COMPILER_IDS,
)
@pytest.mark.parametrize(
    "formula_factory",
    [
        pytest.param(TRUE, id="true"),
        pytest.param(FALSE, id="false"),
        pytest.param(lambda: And(Symbol("p"), Or(Not(Symbol("q")), Symbol("r"))), id="compound"),
    ],
)
def test_native_round_trip_preserves_meaning(
    env: Environment,
    tmp_path: Path,
    compiler_type: Callable[[], PropCompiler],
    target_type: PropCompiledTarget,
    formula_factory: FormulaFactoryType,
):
    formula = formula_factory()
    atoms = sorted(formula.get_atoms(), key=lambda atom: atom.symbol_name())
    abstractor = Abstractor({7 * index: atom for index, atom in enumerate(atoms, 1)})
    target = compiler_type().compile(formula, abstractor, all_atoms=atoms)

    directory = tmp_path / "target"
    target.save(directory)
    loaded = target_type.load(directory)
    mgr = env.formula_manager
    reconstructed = loaded.to_pysmt(abstractor, mgr)

    assert equivalent(env, reconstructed, formula)
