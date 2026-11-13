"""Exercise real MathSAT lemmas on the supplied theory corpus."""

from itertools import product

import ddnnife
import pytest
from pysmt.environment import Environment
from pysmt.typing import BOOL, INT, REAL, ArrayType, BVType
from tlemma_enum.solvers import MathSATTotalEnumerator

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4CompiledTarget, D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries import BddEngine, DdnnifeEngine, SddEngine
from tests.test_quantified_compilation import evaluate
from tests.theory_corpus import THEORY_CASES

PAIRINGS = [(BddCompiler, BddEngine), (SddCompiler, SddEngine), (D4Compiler, DdnnifeEngine)]


@pytest.fixture(scope="module", params=THEORY_CASES, ids=lambda case: case.name)
def theory_case(request):
    case = request.param
    with Environment() as env:
        env.enable_infix_notation = True
        mgr = env.formula_manager
        symbols = {name: mgr.Symbol(name, REAL) for name in ("x", "y", "z")}
        symbols.update({name: mgr.Symbol(name, INT) for name in ("i", "j")})
        symbols.update({name: mgr.Symbol(name, BOOL) for name in ("A", "B")})
        symbols.update({name: mgr.Symbol(name, BVType(8)) for name in ("bv1", "bv2")})
        symbols.update({name: mgr.Symbol(name, ArrayType(INT, INT)) for name in ("arr1", "arr2")})
        yield case, env, case.formula_builder(symbols)


@pytest.mark.parametrize("compiler,engine", PAIRINGS)
@pytest.mark.parametrize("strategy", ["compile_treduced", "compile_textended"])
@pytest.mark.parametrize("projection", ["all", "theory"])
def test_corpus_semantics_and_queries(theory_case, compiler, engine, strategy, projection, tmp_path):
    case, env, raw_phi = theory_case
    mgr = env.formula_manager
    projection_atoms = (
        None if projection == "all" else [atom for atom in raw_phi.get_atoms() if not atom.is_symbol(BOOL)]
    )
    if projection == "theory" and any(atom.is_symbol(BOOL) for atom in raw_phi.get_atoms()):
        with pytest.raises(ValueError, match="formula atoms"):
            TheoryCompilation(raw_phi, projection_atoms, env=env)
        return
    with TheoryCompilation(raw_phi, projection_atoms, env=env) as compilation:
        phi = compilation.phi
        selected = compilation.all_vars
        atoms = tuple(sorted(phi.get_atoms() | set(selected), key=lambda atom: atom.node_id()))
        rows = []
        with env.factory.Solver(name="msat") as solver:
            for values in product((False, True), repeat=len(atoms)):
                assignment = dict(zip(atoms, values))
                cube = mgr.And([atom if value else mgr.Not(atom) for atom, value in assignment.items()])
                rows.append((assignment, evaluate(mgr, phi, assignment), solver.is_sat(cube)))
        models = [assignment for assignment, truth, consistent in rows if truth and consistent]
        assert len(models) == case.model_count
        theory_atoms = tuple(atom for atom in atoms if not atom.is_symbol(BOOL))
        if theory_atoms:
            assert (
                len({tuple(assignment[atom] for atom in theory_atoms) for assignment in models})
                == case.projected_model_count
            )
        expected = {
            tuple(assignment[atom] for atom in selected)
            for assignment, truth, consistent in rows
            if (truth and consistent if strategy == "compile_treduced" else truth or not consistent)
        }
        enumerator = MathSATTotalEnumerator()
        try:
            enumerator.check_all_sat(
                phi if strategy == "compile_treduced" else mgr.Not(phi), atoms=compilation.all_vars
            )
            lemmas = enumerator.get_theory_lemmas()
        finally:
            enumerator._solver.exit()
        generated = set().union(*(compilation.normalize(lemma).get_atoms() for lemma in lemmas)) - set(atoms)
        if compiler is D4Compiler and strategy == "compile_textended" and generated:
            with pytest.raises(NotImplementedError, match="universal"):
                compilation.compile_textended(compiler(), lemmas)
            return
        target = getattr(compilation, strategy)(compiler(), lemmas)
    path = tmp_path / "artifact"
    target.save(path)
    loaded = TheoryCompiledTarget.load(path, type(target.target), env=env)
    for artifact in (target, loaded):
        reconstructed = artifact.to_pysmt()
        assert reconstructed.get_atoms() <= set(selected)
        for values in product((False, True), repeat=len(selected)):
            assert evaluate(mgr, reconstructed, dict(zip(selected, values))) == (values in expected), case.name
        # Preserve the existing ddnnife terminal-circuit exclusion.
        if isinstance(artifact.target, D4CompiledTarget) and artifact.target.nnf_text in ("t 1\n", "f 1\n"):
            with pytest.raises(ddnnife.InternalError):
                artifact.queries(engine)
            continue
        with artifact.queries(engine) as queries:
            assert queries.count_truth_assignments() == len(expected)
            assert queries.is_satisfiable() == bool(expected)
            assert queries.is_valid() == (len(expected) == 2 ** len(selected))
            actual = list(queries.enumerate_truth_assignments())
            assert len(actual) == len(expected)
            assert {tuple(assignment[atom] for atom in selected) for assignment in actual} == expected
            for atom in selected:
                position = selected.index(atom)
                for value in (False, True):
                    literal = atom if value else mgr.Not(atom)
                    matching = {values for values in expected if values[position] == value}
                    assert queries.count_truth_assignments([literal]) == len(matching)
                    assert queries.entails_clause(literal) == (matching == expected)
                    assert queries.is_implicant(literal) == (len(matching) == 2 ** (len(selected) - 1))
