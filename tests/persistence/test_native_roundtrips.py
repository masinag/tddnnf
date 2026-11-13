"""Native backend save/load preserves semantics across the full projected formula bank."""

from tests.support import equivalent


def test_save_load_roundtrip_equivalence(mgr, compiler, bank_case, tmp_path):
    target = compiler.compile(
        bank_case.original_formula,
        bank_case.abstr,
        all_atoms=bank_case.all_atoms,
        exists_atoms=bank_case.vars_to_forget,
    )
    target.save(tmp_path / "artifact")
    loaded = type(target).load(tmp_path / "artifact")
    equivalent(mgr, loaded.to_pysmt(bank_case.abstr, mgr), target.to_pysmt(bank_case.abstr, mgr))
