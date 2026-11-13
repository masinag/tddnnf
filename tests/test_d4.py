import pytest

from tddnnf.compilers.d4 import D4_BIN, D4CompiledTarget, D4Compiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries import DdnnifeEngine
from tests._base_compiler_test import BaseTestCompiler

pytestmark = pytest.mark.skipif(
    not D4_BIN.is_file(),
    reason="d4 binary not installed (run: python -m tddnnf.install_bin --d4)",
)


class TestD4Compiler(BaseTestCompiler):
    compiler_cls = D4Compiler
    target_cls = D4CompiledTarget


@pytest.mark.parametrize("injected", [False, True], ids=["native", "leftover-literals"])
def test_projection_cleanup(mgr, a, b, c, monkeypatch, tmp_path, injected):
    forgotten = mgr.Symbol("forgotten")
    abstr = Abstractor({3: a, 7: b, 11: c, 15: forgotten})
    formula = mgr.And(a, mgr.Not(c), forgotten)
    projection = [c, b, a]
    cleaned = "a 1 0\nt 2 0\nt 3 0\n1 2 1 -3 0\n1 3 0\n"
    if injected:
        raw = "a 1 0\nt 2 0\nt 3 0\n1 2 1 -3 4 -9 0\n1 3 9 -12 0\n"

        def run_d4(circuit_path, out_path):
            assert "P v3 v7 v11\n" in circuit_path.read_text()
            out_path.write_text(raw)

        monkeypatch.setattr(D4Compiler, "_run_d4", staticmethod(run_d4))

    native = D4Compiler().compile(
        formula,
        abstr,
        all_atoms=tuple(abstr.atom_to_id),
        exists_atoms=[atom for atom in abstr.atom_to_id if atom not in projection],
    )
    assert native.var_count == 3
    assert native.remapping == {3: 1, 7: 2, 11: 3}
    if injected:
        assert native.nnf_text == cleaned

    native.save(tmp_path / "cleaned")
    loaded = D4CompiledTarget.load(tmp_path / "cleaned")
    assert loaded.nnf_text == native.nnf_text
    assert loaded.var_count == native.var_count
    assert loaded.remapping == native.remapping
    for target in (native, loaded):
        reconstructed = target.to_pysmt(abstr, mgr)
        with mgr.env.factory.Solver() as solver:
            solver.add_assertion(mgr.Not(mgr.Iff(reconstructed, mgr.And(a, mgr.Not(c)))))
            assert not solver.solve()
        container = TheoryCompiledTarget(target, abstr, projection, env=mgr.env)
        with container.queries(DdnnifeEngine) as queries:
            models = list(queries.enumerate_truth_assignments())
            assert len(models) == len({frozenset(m.items()) for m in models}) == 2
            assert queries.count_truth_assignments() == len(models)
            assert all(tuple(m) == tuple(projection) for m in models)
            assert {tuple(m.values()) for m in models} == {(False, False, True), (False, True, True)}
            assert queries.count_truth_assignments([b]) == queries.count_truth_assignments([mgr.Not(b)]) == 1
            assert queries.count_truth_assignments([mgr.Not(a)]) == 0
