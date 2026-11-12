"""Schema validation and propagation of missing artifact files."""

import json

import pytest
from pysdd.sdd import SddManager

from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.compilers.pysdd import SddCompiledTarget
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.persistence import read_json


@pytest.mark.parametrize("container_load", [False, True])
@pytest.mark.parametrize("version, message", [(None, "migration"), (999, "schema version"), (True, "schema version")])
def test_invalid_schema_version(artifact, version, message, container_load):
    path, original = artifact
    data = read_json(path / "metadata.json")
    if version is None:
        del data["schema_version"]
    else:
        data["schema_version"] = version
    (path / "metadata.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match=message):
        if container_load:
            TheoryCompiledTarget.load(path, type(original.target))
        else:
            type(original.target).load(path)


@pytest.mark.parametrize("filename", ["abstraction.json", "circuit.nnf"])
def test_missing_artifact_file_propagates(tmp_path, mgr, filename):
    path = tmp_path / "target"
    TheoryCompiledTarget(D4CompiledTarget("t 1\n", 0), Abstractor(), [], mgr.env).save(path)
    (path / filename).unlink()
    with pytest.raises(FileNotFoundError, match=filename):
        TheoryCompiledTarget.load(path, D4CompiledTarget)


def test_missing_sdd_vtree_file_propagates(tmp_path):
    manager = SddManager(var_count=1)
    path = tmp_path / "target"
    SddCompiledTarget(manager.literal(1), manager, {1: 1}).save(path)
    (path / "circuit.vtree").unlink()
    with pytest.raises(FileNotFoundError, match="circuit.vtree"):
        SddCompiledTarget.load(path)
