"""Formula builders and expected model counts for integration tests."""

import pytest
from pysmt.shortcuts import Array, Int, Real, ToReal
from pysmt.typing import INT

BANK_CASES = [
    pytest.param(lambda s: (s["A"] | s["B"]) & (~s["A"] | ~s["B"]), 2, id="Bool only"),
    pytest.param(lambda s: s["x"].Equals(s["y"]) & s["x"].Equals(s["z"]) & ~s["y"].Equals(s["z"]), 0, id="Eq unsat"),
    pytest.param(lambda s: (s["x"] <= 0) & (s["x"] >= 1), 0, id="LRA unsat"),
    pytest.param(lambda s: s["x"].Equals(0) & (s["x"] + 1).Equals(0), 0, id="LRA unsat eq"),
    pytest.param(lambda s: (s["x"] >= 0) ^ (s["x"] <= 1), 2, id="LRA no lemmas"),
    pytest.param(lambda s: (s["x"] <= 0) | (s["x"] >= 1), 2, id="LRA disj lemma"),
    pytest.param(lambda s: (s["x"] + s["y"] >= 1) | (s["x"] + s["y"] <= 0), 2, id="LRA two vars"),
    pytest.param(
        lambda s: ((s["x"] + s["y"] >= 1) & s["A"]) | ((s["x"] + s["y"] <= 0) & ~s["A"]), 2, id="LRA+Bool simple"
    ),
    pytest.param(
        lambda s: (s["A"] | (s["x"] > 0)) & (~s["A"] | (s["x"] < 0)) & s["x"].Equals(0), 0, id="LRA+Bool unsat"
    ),
    pytest.param(lambda s: (~s["A"] | (s["x"] + s["y"] >= 1)) & (~s["B"] | (s["x"] <= 0)), 9, id="LRA+Bool proj"),
    pytest.param(
        lambda s: ~s["x"].Equals(s["y"]) | ((s["x"] >= Real(1)) & (s["x"] + s["y"] <= Real(0))), 4, id="LRA eq lemma"
    ),
    pytest.param(lambda s: (s["x"] >= 0.5) & (s["x"] <= 1.5) & ToReal(s["i"]).Equals(s["x"]), 1, id="LIRA simple"),
    pytest.param(lambda s: (s["x"] + ToReal(s["i"]) >= 2.5) | (ToReal(s["i"]) <= 0.5), 3, id="LIRA disj"),
    pytest.param(
        lambda s: (
            ((s["x"] + ToReal(s["i"]) >= 3.5) & (s["y"] <= 1.0)) | (s["A"] & (s["x"] + 2 * ToReal(s["i"]) <= 0.0))
        ),
        7,
        id="LIRA complex",
    ),
    pytest.param(lambda s: (ToReal(s["i"]) > 1) & (ToReal(s["i"]) < 2), 0, id="LIRA unsat"),
    pytest.param(
        lambda s: (s["x"] + s["y"] < 5) & (s["x"] + s["y"] > 10) & s["y"].Equals(s["x"] + 1), 0, id="LIRA unsat 2 vars"
    ),
    pytest.param(
        lambda s: (~s["A"] & (2 * s["i"]).Equals(3 * s["j"])) | ((s["i"] < 10) & (s["i"] + s["j"] > 10)),
        6,
        id="LIRA+Bool",
    ),
    pytest.param(
        lambda s: (
            (s["x"] + s["y"] <= 1)
            | (s["x"] >= 2)
            | (s["y"] >= 1)
            | (ToReal(s["i"]) + ToReal(s["j"]) <= 3)
            | (ToReal(s["i"]) >= 4)
            | (ToReal(s["j"]) >= 2)
            | (s["z"] <= 0)
            | (s["z"] >= 1)
        ),
        146,
        id="LIRA atoms partitionable",
    ),
    pytest.param(
        lambda s: s["bv2"].Equals(1) & ~(s["bv1"] + s["bv2"]).Equals(0) | s["bv1"].Equals(255), 3, id="BV lemma"
    ),
    pytest.param(lambda s: (s["bv1"] + s["bv2"] < 10) | (s["bv1"] + s["bv2"] > 20), 2, id="BV disj"),
    pytest.param(lambda s: (s["bv1"] - 1).Equals(127) & ~s["bv1"].Equals(128), 0, id="BV unsat"),
    pytest.param(
        lambda s: (s["bv1"] ^ 1).Equals(0) & ((s["bv1"] & 2).Equals(2) | s["bv1"].BVSGE(0)), 1, id="BV disj one side"
    ),
    pytest.param(
        lambda s: ~s["arr1"].Select(s["i"]).Equals(s["j"]) | ~s["arr2"].Equals(s["arr1"].Store(s["i"], s["j"])),
        3,
        id="Arrays select-store",
    ),
    pytest.param(
        lambda s: (
            (
                s["arr1"].Select(Int(0)).Equals(s["arr2"].Select(Int(0)))
                & ~s["arr1"].Equals(s["arr2"])
                & s["arr1"].Equals(Array(INT, Int(0)).Store(s["i"], Int(1)))
                & s["arr2"].Equals(Array(INT, Int(0)).Store(s["j"], Int(1)))
            )
            | s["i"].Equals(s["j"])
        ),
        9,
        id="Arrays extensionality",
    ),
    pytest.param(lambda s: s["arr1"].Store(s["i"], Int(1)).Select(s["i"]).Equals(0), 0, id="Arrays unsat"),
    pytest.param(
        lambda s: (
            s["arr1"].Select(s["i"]).Equals(s["j"])
            | (
                s["j"].Equals(s["j"])
                | s["arr2"].Store(s["i"], s["j"] + 1).Select(s["i"]).Equals(s["arr1"].Select(s["i"]))
            )
        ),
        3,
        id="Arrays+LIA simple",
    ),
    pytest.param(
        lambda s: (
            s["arr1"].Select(s["i"]).Equals(s["j"])
            & s["arr2"].Equals(s["arr1"].Store(s["i"], s["j"] + 1))
            & s["arr2"].Select(s["i"]).Equals(s["arr1"].Select(s["i"]))
        ),
        0,
        id="Arrays+LRA unsat",
    ),
]
