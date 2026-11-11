"""SDD persistence preserves sparse atom IDs and requires mapping metadata."""

import json

import pytest
from pysdd.sdd import SddManager

from tddnnf.compilers.d4 import D4CompiledTarget, D4Compiler
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


def test_sdd_roundtrip_preserves_sparse_atom_ids(mgr, a, b, tmp_path):
    abstr = Abstractor({7: a, 1000: b})
    formula = mgr.And(a, mgr.Not(b))
    target = SddCompiler().compile(formula, abstr)
    path = tmp_path / "target"

    target.save(path)
    loaded = SddCompiledTarget.load(path)

    equivalent(mgr, loaded.to_pysmt(abstr, mgr), formula)


def test_d4_roundtrip_preserves_sparse_atom_ids(mgr, a, b, tmp_path):
    abstr = Abstractor({7: a, 1000: b})
    formula = mgr.And(a, mgr.Not(b))
    target = D4Compiler().compile(formula, abstr)
    path = tmp_path / "target"

    target.save(path)
    loaded = D4CompiledTarget.load(path)

    equivalent(mgr, loaded.to_pysmt(abstr, mgr), formula)
