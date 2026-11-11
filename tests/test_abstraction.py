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

    def test_registration_preserves_ids_and_read_only_views(self, a, b, c):
        source = {7: a, 2: b}
        abstr = Abstractor(source)
        ids, atoms = abstr.id_to_atom, abstr.atom_to_id
        source[7] = c
        assert abstr.get_id(a) == 7
        assert abstr.get_id(b) == 2
        assert abstr.get_id(c) == 8
        assert abstr.get_id(c) == 8
        assert dict(ids) == {7: a, 2: b, 8: c}
        assert dict(atoms) == {a: 7, b: 2, c: 8}
        assert abstr.max_var == 8
        assert abstr.var_count == 3
        with pytest.raises(TypeError):
            ids[7] = c
        with pytest.raises(TypeError):
            del atoms[a]
        with pytest.raises(AttributeError):
            abstr.id_to_atom = {}
        with pytest.raises(AttributeError):
            abstr.atom_to_id = {}

    def test_registration_starts_at_one(self, abstr, a, b):
        assert abstr.get_id(a) == 1
        assert abstr.get_id(b) == 2
        assert abstr.get_id(a) == 1

    def test_registration_rejects_non_atom(self, abstr, mgr, a, b):
        with pytest.raises(AssertionError, match="atom"):
            abstr.get_id(mgr.And(a, b))
        assert abstr.var_count == 0

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
