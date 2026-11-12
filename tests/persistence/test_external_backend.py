"""Structural external backends control persistence, validation, and exceptions."""

import json
from typing import assert_type
from unittest.mock import patch

import pytest

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import DagSize, PropCompiledTarget
from tddnnf.core.persistence import read_json, read_metadata, saving_to, write_metadata


class LiteralTarget:
    """Structural backend with its own representation, codec, and payload."""

    def __init__(self, atom_id: int):
        self.atom_id = atom_id

    def dag_size(self):
        return DagSize(1, 0)

    def to_pysmt(self, abstr, mgr):
        return abstr.get_atom(self.atom_id)

    def save(self, directory):
        with saving_to(directory) as temporary:
            temporary.mkdir()
            (temporary / "literal.txt").write_text(str(self.atom_id))
            write_metadata(temporary, "literal", codec="integer-text", files=["literal.txt"])

    @classmethod
    def load(cls, directory):
        read_metadata(directory)
        return cls(int((directory / "literal.txt").read_text()))


def test_external_backend_roundtrip(tmp_path, mgr):
    atom, absent = mgr.Symbol("atom"), mgr.Symbol("absent")
    original = TheoryCompiledTarget(LiteralTarget(7), Abstractor({7: atom, 11: absent}), [absent, atom], mgr.env)
    path = tmp_path / "custom"
    original.save(path)
    loaded = assert_type(
        TheoryCompiledTarget.load(path, LiteralTarget, env=mgr.env), TheoryCompiledTarget[LiteralTarget]
    )
    assert isinstance(loaded.target, LiteralTarget)
    assert isinstance(loaded.target, PropCompiledTarget)
    assert loaded.target.atom_id == 7
    assert loaded.to_pysmt() is atom
    assert (path / "literal.txt").read_text() == "7"
    assert loaded.dag_size() == DagSize(1, 0)
    assert read_json(path / "metadata.json") == {
        "schema_version": 1,
        "representation": "literal",
        "codec": "integer-text",
        "files": ["literal.txt", "abstraction.json"],
    }


@pytest.mark.parametrize("version", [None, True, 999])
def test_container_delegates_validation_and_propagates_backend_exception(tmp_path, mgr, version):
    path = tmp_path / "custom"
    native = LiteralTarget(7)
    TheoryCompiledTarget(native, Abstractor({7: mgr.Symbol("a")}), [], mgr.env).save(path)
    data = read_json(path / "metadata.json")
    if version is None:
        del data["schema_version"]
    else:
        data["schema_version"] = version
    (path / "metadata.json").write_text(json.dumps(data))
    error = RuntimeError("backend failure")
    with patch.object(LiteralTarget, "load", side_effect=error) as load:
        with pytest.raises(RuntimeError) as caught:
            TheoryCompiledTarget.load(path, LiteralTarget)
    load.assert_called_once_with(path)
    assert caught.value is error
