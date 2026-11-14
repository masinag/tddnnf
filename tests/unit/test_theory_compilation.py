from unittest.mock import Mock

import pytest
from pysmt.environment import Environment
from pysmt.typing import INT

from tddnnf import TheoryCompilation
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import PropCompiledTarget, PropCompiler


@pytest.mark.parametrize("entry", ["formula", "vocabulary", "lemma", "normalize", "abstraction"])
@pytest.mark.parametrize("strategy", ["compile_treduced", "compile_textended"])
def test_rejects_foreign_inputs_before_backend_compilation(env: Environment, entry: str, strategy: str):
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


def test_default_vocabulary_uses_normalized_atoms_in_node_id_order(env: Environment):
    mgr = env.formula_manager
    n = mgr.Symbol("n", INT)
    p = mgr.Symbol("p")
    scaled = mgr.GE(mgr.Times(mgr.Int(2), n), mgr.Int(4))
    with TheoryCompilation(mgr.And(scaled, p), env=env) as compilation:
        lower = mgr.GE(n, mgr.Int(2))
        assert compilation.phi == mgr.And(lower, p)
        assert p.node_id() < lower.node_id()
        assert compilation.atoms == (p, lower)


def test_explicit_vocabulary_normalizes_and_preserves_first_occurrence_order(env: Environment):
    mgr = env.formula_manager
    p, unused = mgr.Symbol("p"), mgr.Symbol("unused")
    n = mgr.Symbol("n", INT)
    scaled = mgr.GE(mgr.Times(mgr.Int(2), n), mgr.Int(4))
    lower = mgr.GE(n, mgr.Int(2))
    atoms = [unused, mgr.Not(scaled), p, lower, mgr.Not(p), unused, mgr.LE(n, n)]
    with TheoryCompilation(mgr.And(p, scaled), atoms=atoms, env=env) as compilation:
        assert compilation.atoms == (unused, lower, p)


@pytest.mark.parametrize("value", [True, False])
def test_empty_vocabulary_accepts_constant_formulas(env, value):
    mgr = env.formula_manager
    with TheoryCompilation(mgr.Bool(value), atoms=[], env=env) as compilation:
        assert compilation.phi == mgr.Bool(value)
        assert compilation.atoms == ()


def test_vocabulary_must_include_every_normalized_formula_atom(env: Environment):
    mgr = env.formula_manager
    p, q = mgr.Symbol("p"), mgr.Symbol("q")
    with pytest.raises(ValueError):
        TheoryCompilation(p, atoms=[], env=env)
    with pytest.raises(ValueError):
        TheoryCompilation(mgr.And(p, q), atoms=[p], env=env)


def test_vocabulary_rejects_constants_compounds_and_underlying_integer_symbols(env: Environment):
    mgr = env.formula_manager
    p, q = mgr.Symbol("p"), mgr.Symbol("q")
    for invalid in (mgr.TRUE(), mgr.FALSE(), mgr.And(p, q), mgr.Symbol("n", INT)):
        with pytest.raises(ValueError):
            TheoryCompilation(p, atoms=[p, invalid], env=env)


@pytest.mark.parametrize("strategy", ["compile_treduced", "compile_textended"])
def test_builders_pass_normalized_formula_vocabulary_and_quantifiers(env: Environment, strategy: str):
    mgr = env.formula_manager
    p, unused, generated = (mgr.Symbol(name) for name in ("p", "unused", "generated"))
    n = mgr.Symbol("n", INT)
    scaled = mgr.GE(mgr.Times(mgr.Int(2), n), mgr.Int(4))
    lower = mgr.GE(n, mgr.Int(2))
    lemma = mgr.Or(mgr.Not(scaled), generated)
    normalized_lemma = mgr.Or(mgr.Not(lower), generated)
    compiler = Mock(spec=PropCompiler)
    artifact = Mock(spec=PropCompiledTarget)
    compiler.compile.return_value = artifact
    with TheoryCompilation(mgr.And(p, scaled), atoms=[unused, scaled, p], env=env) as compilation:
        result = getattr(compilation, strategy)(compiler, [lemma, p])
        extended = strategy == "compile_textended"
        combined = (
            mgr.Or(mgr.And(p, lower), mgr.Not(normalized_lemma), mgr.Not(p))
            if extended
            else mgr.And(mgr.And(p, lower), normalized_lemma, p)
        )
        compiler.compile.assert_called_once_with(
            combined,
            result.abstr,
            all_atoms=(unused, lower, p, generated),
            exists_atoms=() if extended else (generated,),
            forall_atoms=(generated,) if extended else (),
            computation_logger=None,
        )
        assert dict(result.abstr.id_to_atom) == {1: unused, 2: lower, 3: p, 4: generated}
    assert result.target is artifact
    assert result.atoms == (unused, lower, p)
    assert result.env is env


def test_reduced_compilation_preserves_and_extends_supplied_sparse_abstraction(env: Environment):
    mgr = env.formula_manager
    p, unused, generated = (mgr.Symbol(name) for name in ("p", "unused", "generated"))
    abstractor = Abstractor({3: unused, 8: p})
    compiler = Mock(spec=PropCompiler)
    compiler.compile.return_value = Mock(spec=PropCompiledTarget)
    with TheoryCompilation(p, env=env) as compilation:
        result = compilation.compile_treduced(compiler, [mgr.Or(p, generated)], abstractor=abstractor)
    assert result.abstr is abstractor
    assert dict(abstractor.id_to_atom) == {3: unused, 8: p, 9: generated}
    assert compiler.compile.call_args.args[1] is abstractor
    assert compiler.compile.call_args.kwargs["all_atoms"] == (p, generated)
    assert result.atoms == (p,)
