"""Targets retain semantics through owner closure, garbage collection, and abstraction reuse."""

import gc
from contextlib import ExitStack

import ddnnife
import pytest
from pysmt.environment import Environment

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.queries.bdd_engine import BddEngine
from tddnnf.queries.ddnnife_engine import DdnnifeEngine
from tddnnf.queries.sdd_engine import SddEngine
from tests.support import PAIRINGS, STRATEGIES, equivalent


@pytest.mark.parametrize("backend", [BddCompiler, SddCompiler, D4Compiler])
@pytest.mark.parametrize("shape", ["true", "false", "shared"])
def test_bound_target_survives_compilation_and_gc(mgr, backend, shape):
    a, b, c = [mgr.Symbol(name) for name in ("a", "b", "c")]
    shared = mgr.Or(a, b)
    phi = {"true": mgr.TRUE(), "false": mgr.FALSE(), "shared": mgr.Iff(shared, mgr.And(shared, c))}[shape]
    with TheoryCompilation(phi, env=mgr.env) as compilation:
        target = compilation.compile_treduced(backend(), [])
    del compilation
    gc.collect()
    with Environment():
        reconstructed = target.to_pysmt()
        assert reconstructed in mgr.formulae.values()
    equivalent(mgr, reconstructed, phi)
    assert target.env is mgr.env
    if backend is D4Compiler and shape != "shared":
        # ddnnife 0.10 rejects zero-feature files; delegation preserves that limitation.
        with pytest.raises(ddnnife.InternalError, match="fixedbitset size 0"):
            target.dag_size()
    else:
        assert target.dag_size() == target.target.dag_size()


@pytest.mark.parametrize("backend", [BddCompiler, SddCompiler, D4Compiler])
@pytest.mark.parametrize("strategy", ["compile_treduced", "compile_textended"])
def test_shared_abstraction_growth_preserves_earlier_target(mgr, backend, strategy):
    a, b, c, d = [mgr.Symbol(name) for name in ("a", "b", "c", "d")]
    abstr = Abstractor()
    with TheoryCompilation(mgr.Or(a, b), [a, b], env=mgr.env) as compilation:
        first = getattr(compilation, strategy)(backend(), [], abstractor=abstr)
    engine_cls = {BddCompiler: BddEngine, SddCompiler: SddEngine, D4Compiler: DdnnifeEngine}[backend]

    def check_first(query):
        assert query.count_truth_assignments() == 3
        assert query.count_truth_assignments([a]) == 2
        assert query.count_truth_assignments([mgr.Not(a)]) == 1
        assert query.count_truth_assignments([a, a]) == 2
        assert query.count_truth_assignments([a, mgr.Not(a)]) == 0
        assert not query.is_satisfiable([mgr.Not(a), mgr.Not(b)])
        assert query.is_satisfiable([a])
        assert query.entails_clause([a, b])
        assert query.is_implicant([a])
        models = list(query.enumerate_truth_assignments())
        assert len(models) == 3
        assert {frozenset(model.items()) for model in models} == {
            frozenset({a: True, b: True}.items()),
            frozenset({a: True, b: False}.items()),
            frozenset({a: False, b: True}.items()),
        }
        equivalent(mgr, first.to_pysmt(), mgr.Or(a, b))

    with ExitStack() as stack:
        engine = engine_cls(first)
        stack.callback(engine.close)
        check_first(engine)
        with TheoryCompilation(mgr.And(c, d), [d, c], env=mgr.env) as compilation:
            second = getattr(compilation, strategy)(backend(), [], abstractor=abstr)
        assert first.abstr is second.abstr is abstr
        assert dict(abstr.id_to_atom) == {1: a, 2: b, 3: d, 4: c}
        assert first.projection_atoms == (a, b)
        assert second.projection_atoms == (d, c)
        equivalent(mgr, second.to_pysmt(), mgr.And(c, d))
        second_engine = engine_cls(second)
        stack.callback(second_engine.close)
        assert second_engine.count_truth_assignments() == 1
        check_first(engine)
        reopened = engine_cls(first)
        stack.callback(reopened.close)
        check_first(reopened)
        with pytest.raises(ValueError, match="projection atom"):
            engine.count_truth_assignments([c])


@pytest.mark.parametrize("pairing", PAIRINGS)
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_compiler_reuse_preserves_query_results(mgr, pairing, strategy):
    p, q, absent, r = [mgr.Symbol(name) for name in ("p", "q", "absent", "r")]
    compiler = pairing[0]()
    with TheoryCompilation(p, [absent, q, p], env=mgr.env) as compilation:
        first = getattr(compilation, strategy)(compiler, [q])
        second = getattr(compilation, strategy)(compiler, [])
    with TheoryCompilation(r, env=mgr.env) as compilation:
        third = getattr(compilation, strategy)(compiler, [])
    with first.queries(pairing[1]) as query:
        assert query.count_truth_assignments() == (2 if strategy == "compile_treduced" else 6)
    with second.queries(pairing[1]) as query:
        assert query.count_truth_assignments() == 4
    with third.queries(pairing[1]) as query:
        assert query.count_truth_assignments() == 1
