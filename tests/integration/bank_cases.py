"""Formula builders and expected model counts for integration tests."""

from collections.abc import Callable
from dataclasses import dataclass

from pysmt.fnode import FNode
from pysmt.shortcuts import Array, Int, Real, ToReal
from pysmt.typing import INT


@dataclass(frozen=True)
class TCase:
    """A test case with an independent model count."""

    name: str
    formula_builder: Callable[[dict[str, FNode]], FNode]
    model_count: int


BANK_CASES = [
    TCase("Bool only", lambda s: (s["A"] | s["B"]) & (~s["A"] | ~s["B"]), 2),
    TCase("Eq unsat", lambda s: s["x"].Equals(s["y"]) & s["x"].Equals(s["z"]) & ~s["y"].Equals(s["z"]), 0),
    TCase("LRA unsat", lambda s: (s["x"] <= 0) & (s["x"] >= 1), 0),
    TCase("LRA unsat eq", lambda s: s["x"].Equals(0) & (s["x"] + 1).Equals(0), 0),
    TCase("LRA no lemmas", lambda s: (s["x"] >= 0) ^ (s["x"] <= 1), 2),
    TCase("LRA disj lemma", lambda s: (s["x"] <= 0) | (s["x"] >= 1), 2),
    TCase("LRA two vars", lambda s: (s["x"] + s["y"] >= 1) | (s["x"] + s["y"] <= 0), 2),
    TCase("LRA+Bool simple", lambda s: ((s["x"] + s["y"] >= 1) & s["A"]) | ((s["x"] + s["y"] <= 0) & ~s["A"]), 2),
    TCase("LRA+Bool unsat", lambda s: (s["A"] | (s["x"] > 0)) & (~s["A"] | (s["x"] < 0)) & s["x"].Equals(0), 0),
    TCase("LRA+Bool proj", lambda s: (~s["A"] | (s["x"] + s["y"] >= 1)) & (~s["B"] | (s["x"] <= 0)), 9),
    TCase("LRA eq lemma", lambda s: ~s["x"].Equals(s["y"]) | ((s["x"] >= Real(1)) & (s["x"] + s["y"] <= Real(0))), 4),
    TCase("LIRA simple", lambda s: (s["x"] >= 0.5) & (s["x"] <= 1.5) & ToReal(s["i"]).Equals(s["x"]), 1),
    TCase("LIRA disj", lambda s: (s["x"] + ToReal(s["i"]) >= 2.5) | (ToReal(s["i"]) <= 0.5), 3),
    TCase(
        "LIRA complex",
        lambda s: (
            ((s["x"] + ToReal(s["i"]) >= 3.5) & (s["y"] <= 1.0)) | (s["A"] & (s["x"] + 2 * ToReal(s["i"]) <= 0.0))
        ),
        7,
    ),
    TCase("LIRA unsat", lambda s: (ToReal(s["i"]) > 1) & (ToReal(s["i"]) < 2), 0),
    TCase("LIRA unsat 2 vars", lambda s: (s["x"] + s["y"] < 5) & (s["x"] + s["y"] > 10) & s["y"].Equals(s["x"] + 1), 0),
    TCase(
        "LIRA+Bool",
        lambda s: (~s["A"] & (2 * s["i"]).Equals(3 * s["j"])) | ((s["i"] < 10) & (s["i"] + s["j"] > 10)),
        6,
    ),
    TCase(
        "LIRA atoms partitionable",
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
    ),
    TCase("BV lemma", lambda s: s["bv2"].Equals(1) & ~(s["bv1"] + s["bv2"]).Equals(0) | s["bv1"].Equals(255), 3),
    TCase("BV disj", lambda s: (s["bv1"] + s["bv2"] < 10) | (s["bv1"] + s["bv2"] > 20), 2),
    TCase("BV unsat", lambda s: (s["bv1"] - 1).Equals(127) & ~s["bv1"].Equals(128), 0),
    TCase("BV disj one side", lambda s: (s["bv1"] ^ 1).Equals(0) & ((s["bv1"] & 2).Equals(2) | s["bv1"].BVSGE(0)), 1),
    TCase(
        "Arrays select-store",
        lambda s: ~s["arr1"].Select(s["i"]).Equals(s["j"]) | ~s["arr2"].Equals(s["arr1"].Store(s["i"], s["j"])),
        3,
    ),
    TCase(
        "Arrays extensionality",
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
    ),
    TCase("Arrays unsat", lambda s: s["arr1"].Store(s["i"], Int(1)).Select(s["i"]).Equals(0), 0),
    TCase(
        "Arrays+LIA simple",
        lambda s: (
            s["arr1"].Select(s["i"]).Equals(s["j"])
            | (
                s["j"].Equals(s["j"])
                | s["arr2"].Store(s["i"], s["j"] + 1).Select(s["i"]).Equals(s["arr1"].Select(s["i"]))
            )
        ),
        3,
    ),
    TCase(
        "Arrays+LRA unsat",
        lambda s: (
            s["arr1"].Select(s["i"]).Equals(s["j"])
            & s["arr2"].Equals(s["arr1"].Store(s["i"], s["j"] + 1))
            & s["arr2"].Select(s["i"]).Equals(s["arr1"].Select(s["i"]))
        ),
        0,
    ),
]
