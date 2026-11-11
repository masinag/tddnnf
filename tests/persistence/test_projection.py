"""Container serialization preserves ordered projection IDs and bound reconstruction environments."""

import json
from pathlib import Path

from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget


def test_compiled_target_round_trip_preserves_projection_atoms(
    tmp_path: Path, mgr: FormulaManager, a: FNode, b: FNode, abstr: Abstractor
) -> None:
    abstr = Abstractor({1: a, 2: b})
    container = TheoryCompiledTarget(
        D4CompiledTarget("t 1\n", 2, {1: 1, 2: 2}), abstr, projection_atoms=[b, a], env=mgr.env
    )

    tmp_path = tmp_path / "artifact"
    container.save(tmp_path)
    payload = json.loads((tmp_path / "abstraction.json").read_text())
    loaded = TheoryCompiledTarget.load(tmp_path, D4CompiledTarget, env=mgr.env)

    assert payload["projection_atom_ids"] == [abstr.get_id(b), abstr.get_id(a)]
    assert "care_var_ids" not in payload
    assert [atom.serialize() for atom in loaded.projection_atoms] == [b.serialize(), a.serialize()]

    assert loaded.env is mgr.env
    with Environment():
        assert loaded.to_pysmt() is mgr.TRUE()
