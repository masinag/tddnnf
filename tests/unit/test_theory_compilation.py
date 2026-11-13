from unittest.mock import Mock

import pytest
from pysmt.environment import Environment

from tddnnf import TheoryCompilation
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import PropCompiler


@pytest.mark.parametrize("entry", ["formula", "vocabulary", "lemma", "normalize", "abstraction"])
@pytest.mark.parametrize("strategy", ["compile_treduced", "compile_textended"])
def test_rejects_foreign_inputs_before_backend_compilation(env, entry, strategy):
    mgr = env.formula_manager
    local = mgr.Symbol("p")
    foreign = Environment().formula_manager.Symbol("p")
    assert foreign is not local
    compiler = Mock(spec=PropCompiler)
    with pytest.raises(AssertionError, match="selected environment"):
        with TheoryCompilation(
            foreign if entry == "formula" else local,
            atoms=[local, foreign] if entry == "vocabulary" else None,
            env=env,
        ) as compilation:
            if entry == "normalize":
                compilation.normalize(foreign)
            else:
                getattr(compilation, strategy)(
                    compiler,
                    [foreign] if entry == "lemma" else [],
                    abstractor=Abstractor({1: foreign}) if entry == "abstraction" else None,
                )
    compiler.compile.assert_not_called()
