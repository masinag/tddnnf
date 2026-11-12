"""SDD persistence preserves sparse atom IDs and requires mapping metadata."""

import json

import pytest
from pysdd.sdd import SddManager

from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler
from tddnnf.core.abstraction import Abstractor
from tests.support import equivalent


def test_sdd_requires_mapping(tmp_path):
    manager = SddManager(var_count=1)
    path = tmp_path / "target"
    SddCompiledTarget(manager.true(), manager, {}).save(path)
    metadata = path / "metadata.json"
    data = json.loads(metadata.read_text())
    del data["remapping"]
    metadata.write_text(json.dumps(data))
    with pytest.raises(KeyError, match="remapping"):
        SddCompiledTarget.load(path)


@pytest.mark.parametrize("compiler", [SddCompiler, D4Compiler])
def test_roundtrip_preserves_sparse_atom_ids(mgr, a, b, tmp_path, compiler):
    abstr = Abstractor({7: a, 1000: b})
    formula = mgr.And(a, mgr.Not(b))
    target = compiler().compile(formula, abstr)
    path = tmp_path / "target"
    target.save(path)
    loaded = type(target).load(path)
    assert loaded.remapping == target.remapping == {7: 1, 1000: 2}
    equivalent(mgr, loaded.to_pysmt(abstr, mgr), formula)


@pytest.mark.parametrize("compiler", [SddCompiler, D4Compiler])
def test_full_mapping_roundtrip_preserves_unused_entries(mgr, tmp_path, compiler):
    a, forgotten, absent, unrelated = [mgr.Symbol(name) for name in ("a", "forgotten", "absent", "unrelated")]
    abstr = Abstractor({7: forgotten, 1000: a, 2000: absent, 3000: unrelated})
    target = compiler().compile(mgr.And(a, forgotten), abstr, project_on=[absent, a])
    expected = {7: 1, 1000: 2, 2000: 3} if compiler is SddCompiler else {1000: 1, 2000: 2, 7: 3}
    path = tmp_path / "target"
    target.save(path)
    loaded = type(target).load(path)
    assert json.loads((path / "metadata.json").read_text())["remapping"] == {str(k): v for k, v in expected.items()}
    assert loaded.remapping == expected
    equivalent(mgr, loaded.to_pysmt(abstr, mgr), a)
