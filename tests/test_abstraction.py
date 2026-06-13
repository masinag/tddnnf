import pytest
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf.core.abstraction import Abstractor


class TestAbstractor:
    def test_to_dict_keys_are_full_smtlib_scripts(self, mgr: FormulaManager, x: FNode, abstr: Abstractor) -> None:
        abstr.get_id(mgr.GT(x, mgr.Int(5)))

        data = abstr.to_dict()
        key = next(iter(data))
        assert key.startswith("(set-log")
        assert "(declare-fun" in key
        assert "(assert" in key
        assert "(check-sat)" in key

    def test_round_trip_preserves_identity(
        self, env: Environment, mgr: FormulaManager, x: FNode, p: FNode, abstr: Abstractor
    ) -> None:
        a1 = abstr.get_id(mgr.GT(x, mgr.Int(0)))
        a2 = abstr.get_id(p)
        a3 = abstr.get_id(mgr.GT(x, mgr.Int(1)))

        data = abstr.to_dict()
        abstr2 = Abstractor.from_dict(data, env)

        assert abstr2.get_atom(a1) is abstr.get_atom(a1)
        assert abstr2.get_atom(a2) is abstr.get_atom(a2)
        assert abstr2.get_atom(a3) is abstr.get_atom(a3)
        assert abstr2.to_dict() == data

    def test_mixed_theory_types(
        self, env: Environment, mgr: FormulaManager, x: FNode, y_real: FNode, p: FNode, abstr: Abstractor
    ) -> None:
        a1 = abstr.get_id(mgr.GT(x, mgr.Int(3)))
        a2 = abstr.get_id(mgr.GE(y_real, mgr.Real(1.5)))
        a3 = abstr.get_id(p)

        data = abstr.to_dict()
        abstr2 = Abstractor.from_dict(data, env)

        assert abstr2.get_atom(a1) is abstr.get_atom(a1)
        assert abstr2.get_atom(a2) is abstr.get_atom(a2)
        assert abstr2.get_atom(a3) is abstr.get_atom(a3)

    def test_get_id_adds_new_atoms(self, mgr: FormulaManager, x: FNode, abstr: Abstractor) -> None:
        a = mgr.GT(x, mgr.Int(0))
        b = mgr.GT(x, mgr.Int(1))

        idx1 = abstr.get_id(a)
        idx2 = abstr.get_id(b)
        idx3 = abstr.get_id(a)

        assert idx1 == 1
        assert idx2 == 2
        assert idx3 == 1

    def test_get_atom_rejects_negative(self, mgr: FormulaManager, x: FNode, abstr: Abstractor) -> None:
        abstr.get_id(mgr.GT(x, mgr.Int(0)))
        with pytest.raises(ValueError, match="positive"):
            abstr.get_atom(-1)

    def test_get_atom_rejects_zero(self, mgr: FormulaManager, x: FNode, abstr: Abstractor) -> None:
        abstr.get_id(mgr.GT(x, mgr.Int(0)))
        with pytest.raises(ValueError, match="positive"):
            abstr.get_atom(0)

    def test_serialize_bool_symbol(self, mgr: FormulaManager, p: FNode, abstr: Abstractor) -> None:
        abstr.get_id(p)
        data = abstr.to_dict()
        abstr2 = Abstractor.from_dict(data)
        assert abstr2.get_atom(1).is_symbol()
        assert abstr2.get_atom(1).symbol_name() == "p"
