"""d4 projection cleanup, subprocess diagnostics, and temporary-file cleanup."""

import subprocess
from pathlib import Path

import pytest

import tddnnf.compilers.d4 as d4
from tddnnf import TheoryCompilation
from tddnnf.compilers.d4 import D4_BIN, D4Compiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries import DdnnifeEngine
from tests.support import equivalent

pytestmark = pytest.mark.skipif(
    not D4_BIN.is_file(),
    reason="d4 binary not installed (run: python -m tddnnf.install_bin --d4)",
)


def test_projection_cleanup(mgr, a, b, c, monkeypatch):
    forgotten = mgr.Symbol("forgotten")
    abstr = Abstractor({3: a, 7: b, 11: c, 15: forgotten})
    formula = mgr.And(a, mgr.Not(c), forgotten)
    projection = [c, b, a]
    raw = "a 1 0\nt 2 0\nt 3 0\n1 2 1 -3 4 -9 0\n1 3 9 -12 0\n"

    def run_d4(circuit_path, out_path):
        out_path.write_text(raw)

    monkeypatch.setattr(D4Compiler, "_run_d4", staticmethod(run_d4))

    native = D4Compiler().compile(formula, abstr, project_on=projection)
    equivalent(mgr, native.to_pysmt(abstr, mgr), mgr.And(a, mgr.Not(c)))
    container = TheoryCompiledTarget(native, abstr, projection, env=mgr.env)
    with container.queries(DdnnifeEngine) as queries:
        assert queries.count_truth_assignments() == 2
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
