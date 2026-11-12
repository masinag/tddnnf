"""Native backend save/load preserves semantics across the full projected formula bank."""

from tests.support import equivalent


def test_save_load_roundtrip_equivalence(mgr, compiler, bank_case, tmp_path):
    target = compiler.compile(bank_case.original_formula, bank_case.abstr, project_on=bank_case.project_on)
    target.save(tmp_path / "artifact")
    loaded = type(target).load(tmp_path / "artifact")
    equivalent(mgr, loaded.to_pysmt(bank_case.abstr, mgr), target.to_pysmt(bank_case.abstr, mgr))
