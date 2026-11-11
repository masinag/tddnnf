from pathlib import Path

import pytest
from pysmt.formula import FormulaManager
from pysmt.typing import BOOL, INT

from tddnnf import TheoryCompilation, TheoryCompiledTarget
from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler
from tddnnf.queries.sdd_engine import SddEngine


@pytest.mark.parametrize("strategy", ["treduced", "textended"])
def test_compilation_matches_normalized_construction(mgr: FormulaManager, strategy: str) -> None:
    x = mgr.Symbol(f"compilation_context_{strategy}_x", INT)
    p = mgr.Symbol(f"compilation_context_{strategy}_p", BOOL)
    raw_atom = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    raw_lemma = mgr.Or(mgr.Not(p), raw_atom)
    context = TheoryCompilation(p, project_on=[p, raw_atom], env=mgr.env)
    normalized_lemma = context.normalize(raw_lemma)

    with context:
        target = getattr(context, f"compile_{strategy}")(SddCompiler(), [raw_lemma])
        expected = (
            mgr.And(context.phi, normalized_lemma)
            if strategy == "treduced"
            else mgr.Or(context.phi, mgr.Not(normalized_lemma))
        )
    difference = mgr.Not(mgr.Iff(target.to_pysmt(), expected))
    with mgr.env.factory.Solver() as solver:
        solver.add_assertion(difference)
        assert not solver.solve()

    normalized_atom = target.projection_atoms[1]
    assert raw_atom != normalized_atom
    assert raw_atom not in target.abstr
    assert normalized_atom in target.abstr
    assert target.projection_atoms == (p, normalized_atom)


def test_fresh_query_context_handles_direct_and_loaded_targets(
    mgr: FormulaManager,
    tmp_path: Path,
) -> None:
    x = mgr.Symbol("compilation_context_roundtrip_x", INT)
    p = mgr.Symbol("compilation_context_roundtrip_p", BOOL)
    atom = mgr.GE(x, mgr.Int(2))
    equivalent_atom = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    compilation = TheoryCompilation(mgr.And(p, atom), env=mgr.env)
    target = compilation.compile_treduced(SddCompiler(), [])

    tmp_path = tmp_path / "artifact"
    target.save(tmp_path)
    loaded = TheoryCompiledTarget.load(tmp_path, SddCompiledTarget, env=mgr.env)

    for query_target in (target, loaded):
        engine = query_target.queries(SddEngine)
        assert engine.is_satisfiable([equivalent_atom])
        assert not engine.is_satisfiable([mgr.Not(equivalent_atom)])


def test_context_deduplicates_equivalent_projection_atoms(mgr: FormulaManager) -> None:
    x = mgr.Symbol("compilation_context_deduplication_x", INT)
    p = mgr.Symbol("compilation_context_deduplication_p", BOOL)
    atom = mgr.GE(x, mgr.Int(2))
    equivalent_atom = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))

    context = TheoryCompilation(mgr.TRUE(), project_on=[atom, p, equivalent_atom], env=mgr.env)
    canonical_atom = context.normalize(atom)

    assert context.normalize(equivalent_atom) == canonical_atom
    assert context.project_on == (canonical_atom, p)

    target = context.compile_treduced(SddCompiler(), [])

    assert target.projection_atoms == (canonical_atom, p)
    assert SddEngine(target).count_truth_assignments() == 4
