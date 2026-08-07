from pathlib import Path

import pytest
from pysmt.formula import FormulaManager
from pysmt.typing import BOOL, INT

from tddnnf import CompilationContext, QueryContext
from tddnnf.builders.extended import TExtendedBuilder
from tddnnf.builders.reduced import TReducedBuilder
from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries.sdd_engine import SddEngine


@pytest.mark.parametrize("strategy", ["treduced", "textended"])
def test_context_compilation_matches_manual_builder(mgr: FormulaManager, strategy: str) -> None:
    x = mgr.Symbol(f"compilation_context_{strategy}_x", INT)
    p = mgr.Symbol(f"compilation_context_{strategy}_p", BOOL)
    raw_atom = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    raw_lemma = mgr.Or(mgr.Not(p), raw_atom)
    context = CompilationContext(p, project_on=[p, raw_atom], env=mgr.env)
    normalized_lemma = context.normalize(raw_lemma)

    if strategy == "treduced":
        target = context.compile_treduced(SddCompiler, [raw_lemma])
        abstractor = Abstractor()
        manual = TReducedBuilder(SddCompiler(abstractor), env=mgr.env).build(
            context.phi, [normalized_lemma], abstractor, project_on=context.project_on
        )
    else:
        target = context.compile_textended(SddCompiler, [raw_lemma])
        abstractor = Abstractor()
        manual = TExtendedBuilder(SddCompiler(abstractor), env=mgr.env).build(
            context.phi, [normalized_lemma], abstractor, project_on=context.project_on
        )

    difference = mgr.Not(mgr.Iff(target.to_pysmt(mgr), manual.to_pysmt(mgr)))
    with mgr.env.factory.Solver() as solver:
        solver.add_assertion(difference)
        assert not solver.solve()

    normalized_atom = context.normalize(raw_atom)
    assert raw_atom != normalized_atom
    assert raw_atom not in target.abstr
    assert normalized_atom in target.abstr
    assert target.projection_atoms == [p, normalized_atom]


def test_fresh_query_context_handles_direct_and_loaded_targets(
    mgr: FormulaManager,
    tmp_path: Path,
) -> None:
    x = mgr.Symbol("compilation_context_roundtrip_x", INT)
    p = mgr.Symbol("compilation_context_roundtrip_p", BOOL)
    atom = mgr.GE(x, mgr.Int(2))
    equivalent_atom = mgr.GE(mgr.Times(mgr.Int(2), x), mgr.Int(4))
    compilation = CompilationContext(mgr.And(p, atom), env=mgr.env)
    target = compilation.compile_treduced(SddCompiler, [])

    target.save(tmp_path)
    loaded = TheoryCompiledTarget.load(tmp_path, SddCompiledTarget, env=mgr.env)

    for query_target in (target, loaded):
        engine = QueryContext(query_target, env=mgr.env).wrap_queries(SddEngine(query_target))
        assert engine.is_satisfiable([equivalent_atom])
        assert not engine.is_satisfiable([mgr.Not(equivalent_atom)])
