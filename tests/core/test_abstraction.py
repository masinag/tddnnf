"""Stable abstraction IDs, read-only mappings, and SMT-LIB serialization."""

import pytest
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf.core.abstraction import Abstractor


class TestAbstractor:
    @pytest.mark.parametrize("explicit_env", [False, True])
    def test_serialization_preserves_types_identity_and_format(self, env, mgr, x, y_real, p, explicit_env):
        abstr = Abstractor({1: mgr.GT(x, mgr.Int(3)), 2: mgr.GE(y_real, mgr.Real(1.5)), 3: p})
        data = abstr.to_dict()
        for script in data:
            assert script.startswith("(set-log")
            assert "(declare-fun" in script
            assert "(assert" in script
            assert "(check-sat)" in script
        # The default loader must use the active environment's formula interning.
        with env:
            restored = Abstractor.from_dict(data, env) if explicit_env else Abstractor.from_dict(data)
        assert all(restored.get_atom(idx) is atom for idx, atom in abstr.id_to_atom.items())
        assert restored.get_atom(3).is_symbol()
        assert restored.get_atom(3).symbol_name() == "p"
        assert restored.to_dict() == data

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
