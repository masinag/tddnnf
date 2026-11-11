"""SDD persistence requires the native variable mapping in metadata."""

import json

import pytest
from pysdd.sdd import SddManager

from tddnnf.compilers.pysdd import SddCompiledTarget


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
