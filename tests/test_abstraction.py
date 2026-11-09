import json
from pathlib import Path

import pytest
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget


class TestAbstractor:
    def test_to_dict_keys_are_full_smtlib_scripts(self, mgr: FormulaManager, x: FNode, abstr: Abstractor) -> None:
        abstr = Abstractor({1: mgr.GT(x, mgr.Int(5))})

        data = abstr.to_dict()
        key = next(iter(data))
        assert key.startswith("(set-log")
        assert "(declare-fun" in key
        assert "(assert" in key
        assert "(check-sat)" in key

    def test_round_trip_preserves_identity(
        self, env: Environment, mgr: FormulaManager, x: FNode, p: FNode, abstr: Abstractor
    ) -> None:
        a1, a2, a3 = 1, 2, 3
        abstr = Abstractor({1: mgr.GT(x, mgr.Int(0)), 2: p, 3: mgr.GT(x, mgr.Int(1))})

        data = abstr.to_dict()
        abstr2 = Abstractor.from_dict(data, env)

        assert abstr2.get_atom(a1) is abstr.get_atom(a1)
        assert abstr2.get_atom(a2) is abstr.get_atom(a2)
        assert abstr2.get_atom(a3) is abstr.get_atom(a3)
        assert abstr2.to_dict() == data

    def test_mixed_theory_types(
        self, env: Environment, mgr: FormulaManager, x: FNode, y_real: FNode, p: FNode, abstr: Abstractor
    ) -> None:
        a1, a2, a3 = 1, 2, 3
        abstr = Abstractor({1: mgr.GT(x, mgr.Int(3)), 2: mgr.GE(y_real, mgr.Real(1.5)), 3: p})

        data = abstr.to_dict()
        abstr2 = Abstractor.from_dict(data, env)

        assert abstr2.get_atom(a1) is abstr.get_atom(a1)
        assert abstr2.get_atom(a2) is abstr.get_atom(a2)
        assert abstr2.get_atom(a3) is abstr.get_atom(a3)

    def test_unknown_lookup_does_not_register(self, a, b):
        abstr = Abstractor({7: a})
        with pytest.raises(KeyError):
            abstr.get_id(b)
        assert abstr.get_id(a) == 7
        assert dict(abstr.id_to_atom) == {7: a}
        assert abstr.max_var == 7

    def test_get_atom_rejects_negative(self, mgr: FormulaManager, x: FNode, abstr: Abstractor) -> None:
        with pytest.raises(ValueError, match="positive"):
            abstr.get_atom(-1)

    def test_get_atom_rejects_zero(self, mgr: FormulaManager, x: FNode, abstr: Abstractor) -> None:
        with pytest.raises(ValueError, match="positive"):
            abstr.get_atom(0)

    def test_serialize_bool_symbol(self, mgr: FormulaManager, p: FNode, abstr: Abstractor) -> None:
        abstr = Abstractor({1: p})
        data = abstr.to_dict()
        abstr2 = Abstractor.from_dict(data)
        assert abstr2.get_atom(1).is_symbol()
        assert abstr2.get_atom(1).symbol_name() == "p"


def test_compiled_target_round_trip_preserves_projection_atoms(
    tmp_path: Path, mgr: FormulaManager, a: FNode, b: FNode, abstr: Abstractor
) -> None:
    abstr = Abstractor({1: a, 2: b})
    container = TheoryCompiledTarget(D4CompiledTarget("t 1\n", 2), abstr, projection_atoms=[b, a], env=mgr.env)

    container.save(tmp_path)
    payload = json.loads((tmp_path / "abstraction.json").read_text())
    loaded = TheoryCompiledTarget.load(tmp_path, D4CompiledTarget, env=mgr.env)

    assert payload["projection_atom_ids"] == [abstr.get_id(b), abstr.get_id(a)]
    assert "care_var_ids" not in payload
    assert [atom.serialize() for atom in loaded.projection_atoms] == [b.serialize(), a.serialize()]

    assert loaded.env is mgr.env
    with Environment():
        assert loaded.to_pysmt() is mgr.TRUE()
