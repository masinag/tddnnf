"""Public exports, compiler argument validation, and keyword-only abstraction reuse."""

import pytest

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tests.support import STRATEGIES


@pytest.mark.parametrize("bad", ["sdd", SddCompiler, object(), None])
def test_invalid_compiler(mgr, bad):
    with TheoryCompilation(mgr.TRUE(), env=mgr.env) as compilation:
        for strategy in STRATEGIES:
            with pytest.raises(TypeError, match="instance"):
                getattr(compilation, strategy)(bad, [])


def test_public_exports_and_keyword_only_abstraction(mgr):
    import inspect

    import tddnnf
    from tddnnf import TheoryCompiledTarget
    from tddnnf.core.containers import TheoryCompiledTarget as Container
    from tddnnf.queries import BddEngine, DdnnifeEngine, SddEngine

    assert tddnnf.__all__ == ["TheoryCompilation", "TheoryCompiledTarget"]
    assert TheoryCompiledTarget is Container
    assert not hasattr(tddnnf, "CompilationContext")
    assert not hasattr(tddnnf, "QueryContext")
    assert [engine.__name__ for engine in (BddEngine, SddEngine, DdnnifeEngine)] == [
        "BddEngine",
        "SddEngine",
        "DdnnifeEngine",
    ]
    with TheoryCompilation(mgr.Symbol("a"), env=mgr.env) as compilation:
        for method in (compilation.compile_treduced, compilation.compile_textended):
            assert inspect.signature(method).parameters["abstractor"].kind is inspect.Parameter.KEYWORD_ONLY
            with pytest.raises(TypeError):
                method(BddCompiler(), [], {}, Abstractor())
