"""d4 projection cleanup, remapping, subprocess diagnostics, and temporary-file cleanup."""

import subprocess
from pathlib import Path

import pytest

import tddnnf.compilers.d4 as d4
from tddnnf import TheoryCompilation
from tddnnf.compilers.d4 import D4_BIN, D4CompiledTarget, D4Compiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries import DdnnifeEngine
from tests.support import equivalent

pytestmark = pytest.mark.skipif(
    not D4_BIN.is_file(),
    reason="d4 binary not installed (run: python -m tddnnf.install_bin --d4)",
)


@pytest.mark.parametrize("injected", [False, True], ids=["native", "leftover-literals"])
def test_projection_cleanup(mgr, a, b, c, monkeypatch, tmp_path, injected):
    forgotten = mgr.Symbol("forgotten")
    abstr = Abstractor({3: a, 7: b, 11: c, 15: forgotten})
    formula = mgr.And(a, mgr.Not(c), forgotten)
    projection = [c, b, a]
    cleaned = "a 1 0\nt 2 0\nt 3 0\n1 2 1 -3 0\n1 3 0\n"
    if injected:
        raw = "a 1 0\nt 2 0\nt 3 0\n1 2 1 -3 4 -9 0\n1 3 9 -12 0\n"

        def run_d4(circuit_path, out_path):
            assert "P v1 v2 v3\n" in circuit_path.read_text()
            out_path.write_text(raw)

        monkeypatch.setattr(D4Compiler, "_run_d4", staticmethod(run_d4))

    native = D4Compiler().compile(formula, abstr, project_on=projection)
    assert native.var_count == 3
    assert native.remapping == {3: 1, 7: 2, 11: 3, 15: 4}
    if injected:
        assert native.nnf_text == cleaned

    native.save(tmp_path / "cleaned")
    loaded = D4CompiledTarget.load(tmp_path / "cleaned")
    assert loaded.nnf_text == native.nnf_text
    assert loaded.var_count == native.var_count
    assert loaded.remapping == native.remapping
    for target in (native, loaded):
        reconstructed = target.to_pysmt(abstr, mgr)
        with mgr.env.factory.Solver() as solver:
            solver.add_assertion(mgr.Not(mgr.Iff(reconstructed, mgr.And(a, mgr.Not(c)))))
            assert not solver.solve()
        container = TheoryCompiledTarget(target, abstr, projection, env=mgr.env)
        with container.queries(DdnnifeEngine) as queries:
            models = list(queries.enumerate_truth_assignments())
            assert len(models) == len({frozenset(m.items()) for m in models}) == 2
            assert queries.count_truth_assignments() == len(models)
            assert all(tuple(m) == tuple(projection) for m in models)
            assert {tuple(m.values()) for m in models} == {(False, False, True), (False, True, True)}
            assert queries.count_truth_assignments([b]) == queries.count_truth_assignments([mgr.Not(b)]) == 1
            assert queries.count_truth_assignments([mgr.Not(a)]) == 0


def test_d4_failure_diagnostics_and_cleanup(mgr, monkeypatch):
    observed = []

    def fail(cmd, **kwargs):
        circuit = Path(cmd[cmd.index("-i") + 1])
        assert circuit.exists()
        observed.append(circuit.parent)
        return subprocess.CompletedProcess(cmd, 23, b"stdout", b"native diagnostic")

    monkeypatch.setattr(d4.subprocess, "run", fail)
    with TheoryCompilation(mgr.Symbol("a"), env=mgr.env) as compilation:
        with pytest.raises(RuntimeError, match=r"exit 23.*\n.*native diagnostic"):
            compilation.compile_treduced(D4Compiler(), [])
    assert observed and all(not path.exists() for path in observed)


def test_projection_remaps_atoms_before_forgotten_atoms(mgr, a, b, c):
    abstr = Abstractor({3: b, 7: a, 1000: c})

    native = D4Compiler().compile(mgr.And(a, mgr.Not(b)), abstr, project_on=[c, a])

    equivalent(mgr, native.to_pysmt(abstr, mgr), a)
    container = TheoryCompiledTarget(native, abstr, [c, a], env=mgr.env)
    with container.queries(DdnnifeEngine) as query:
        assert query.count_truth_assignments() == 2
        assert query.count_truth_assignments([mgr.Not(a)]) == 0


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("shape", ["sat", "unsat"])
def test_full_mapping_on_constant_return_paths(mgr, a, b, c, project, shape):
    abstr = Abstractor({3: a, 7: b, 11: c})
    formula = a if shape == "sat" else mgr.And(a, mgr.Not(a))
    projection = [b] if project else []
    native = D4Compiler().compile(formula, abstr, project_on=projection)
    assert native.remapping == ({7: 1, 3: 2} if project else {3: 1})
    assert native.var_count == (1 if project and shape == "sat" else 0)
    if not project or shape == "unsat":
        assert native.nnf_text == ("t 1\n" if shape == "sat" else "f 1\n")
