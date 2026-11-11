"""Direct and loaded containers accept equivalent theory syntax in fresh sessions."""

from pathlib import Path

from pysmt.formula import FormulaManager
from pysmt.typing import BOOL, INT

from tddnnf import TheoryCompilation, TheoryCompiledTarget
from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler
from tddnnf.queries.sdd_engine import SddEngine


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
