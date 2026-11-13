"""d4 projection cleanup, subprocess diagnostics, and temporary-file cleanup."""

import subprocess
from pathlib import Path

import pytest

import tddnnf.compilers.d4 as d4
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.core.abstraction import Abstractor
from tests.support import equivalent


def test_projection_cleanup(mgr, a, b, c, monkeypatch):
    forgotten = mgr.Symbol("forgotten")
    abstr = Abstractor({3: a, 7: b, 11: c, 15: forgotten})
    formula = mgr.And(a, mgr.Not(c), forgotten)
    projection = [c, b, a]
    raw = "a 1 0\nt 2 0\nt 3 0\n1 2 1 -3 4 -9 0\n1 3 9 -12 0\n"

    def run_d4(circuit_path, out_path):
        out_path.write_text(raw)

    monkeypatch.setattr(D4Compiler, "_run_d4", staticmethod(run_d4))

    native = D4Compiler().compile(formula, abstr, all_atoms=[*projection, forgotten], exists_atoms=[forgotten])
    equivalent(mgr, native.to_pysmt(abstr, mgr), mgr.And(a, mgr.Not(c)))


def test_d4_failure_diagnostics_and_cleanup(mgr, monkeypatch):
    observed = []

    def fail(cmd, **kwargs):
        circuit = Path(cmd[cmd.index("-i") + 1])
        assert circuit.exists()
        observed.append(circuit.parent)
        return subprocess.CompletedProcess(cmd, 23, b"stdout", b"native diagnostic")

    monkeypatch.setattr(d4.subprocess, "run", fail)
    atom = mgr.Symbol("a")
    with pytest.raises(RuntimeError, match=r"exit 23.*\n.*native diagnostic"):
        D4Compiler().compile(atom, Abstractor({1: atom}), all_atoms=[atom])
    assert observed and all(not path.exists() for path in observed)
