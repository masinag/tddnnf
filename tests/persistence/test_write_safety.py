"""Overwrite refusal, partial-write cleanup, and saves without reloading state."""

import pytest

from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget


def test_overwrite_refusal(artifact):
    path, original = artifact
    before = (path / "metadata.json").read_bytes()
    with pytest.raises(FileExistsError):
        original.save(path)
    assert (path / "metadata.json").read_bytes() == before


def test_failure_cleanup(tmp_path, monkeypatch):
    target = D4CompiledTarget("t 1\n", 0)
    original = type(tmp_path).write_text

    def fail_payload(path, *args, **kwargs):
        if path.name == "circuit.nnf":
            raise OSError("write failed")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), "write_text", fail_payload)
    with pytest.raises(OSError, match="write failed"):
        target.save(tmp_path / "bad")
    assert not list(tmp_path.iterdir())


def test_save_does_not_reload_state(tmp_path, monkeypatch, mgr):
    def forbidden(*args, **kwargs):
        pytest.fail("Saving must not reconstruct saved state")

    monkeypatch.setattr(D4CompiledTarget, "load", forbidden)
    monkeypatch.setattr(Abstractor, "from_dict", forbidden)
    target = TheoryCompiledTarget(D4CompiledTarget("t 1\n", 0), Abstractor(), [], mgr.env)
    target.save(tmp_path / "target")
