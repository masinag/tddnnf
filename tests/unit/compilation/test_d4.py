import subprocess
from pathlib import Path
from typing import Literal
from unittest.mock import patch

import pytest
from pysmt.environment import Environment
from pysmt.shortcuts import And, Symbol

from tddnnf.compilation.d4 import D4Compiler
from tddnnf.core.abstraction import Abstractor

ModeType = Literal["circuit", "cnf"]


@pytest.mark.parametrize("mode", ["circuit", "cnf"])
def test_d4_rejects_universal_elimination(env: Environment, mode: ModeType):
    p, q = (Symbol(name) for name in ("p", "q"))
    abstractor = Abstractor()
    for atom in (p, q):
        abstractor.get_id(atom)

    with pytest.raises(NotImplementedError):
        D4Compiler(input_mode=mode).compile(And(p, q), abstractor, all_atoms=[p, q], forall_atoms=[q])


@pytest.mark.parametrize("mode", ["circuit", "cnf"])
@pytest.mark.parametrize("override", [[], ["--remove-gates", "0"], ["--remove-gates=0"]])
def test_d4_argument_forwarding_and_snapshot(mode: ModeType, override: list[str]):
    options = [*override, "--some-option", "literal argument; $HOME"]
    compiler = D4Compiler(input_mode=mode, options=options)
    options.append("later")
    with patch("tddnnf.compilation.d4.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run:
        compiler._run_d4(Path("input file"), Path("output file"))
    cmd = run.call_args.args[0]
    assert cmd[1:7] == ["-i", "input file", "--input-type", mode, "--dump-file", "output file"]
    default = ["--remove-gates", "1"] if mode == "circuit" and not override else []
    assert cmd[7:] == default + options[:-1]


def test_d4_constructor_validation():
    assert D4Compiler().input_mode == "circuit"
    with pytest.raises(ValueError, match="Unsupported"):
        D4Compiler(input_mode="invalid")  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("mode", ["circuit", "cnf"])
def test_d4_failure_propagation_and_temporary_cleanup(env: Environment, mode: ModeType):
    p = Symbol("p")
    abstractor = Abstractor({1: p})
    paths = []

    def fail(cmd, **kwargs):
        paths.append(Path(cmd[2]))
        assert paths[-1].exists()
        return subprocess.CompletedProcess(cmd, 7, stderr=b"native failure")

    with patch("tddnnf.compilation.d4.subprocess.run", side_effect=fail):
        with pytest.raises(RuntimeError, match=r"exit 7.*\n.*native failure"):
            D4Compiler(input_mode=mode).compile(p, abstractor, all_atoms=[p])
    assert paths and not paths[0].parent.exists()
