import json
from pathlib import Path
from typing import assert_type

import pytest
from dd.cudd import BDD
from pysdd.sdd import SddManager, Vtree
from pysmt.environment import Environment

from tddnnf.compilers.cudd import BddCompiledTarget
from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.compilers.pysdd import SddCompiledTarget
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import DagSize, PropCompiledTarget
from tddnnf.core.persistence import read_json, read_metadata, saving_to, write_metadata


@pytest.fixture(params=["obdd", "sdd", "ddnnf"])
def artifact(request, mgr, tmp_path):
    a, inactive, absent = [mgr.Symbol(name) for name in ("a", "inactive", "absent")]
    abstr = Abstractor({3: a, 7: inactive, 11: absent})
    rep = request.param
    if rep == "obdd":
        manager = BDD()
        manager.declare(*(f"b{i}" for i in range(1, 12)))
        manager.reorder({f"b{i}": 11 - i for i in range(1, 12)})
        native = BddCompiledTarget(manager.var("b3"), manager)
    elif rep == "sdd":
        tree = Vtree(var_count=11, vtree_type="left")
        manager = SddManager.from_vtree(tree)
        manager.auto_gc_and_minimize_off()
        native = SddCompiledTarget(manager.literal(3), manager)
    else:
        native = D4CompiledTarget("o 1 0\nt 2 0\n1 2 1 0\n", 2, {3: 1, 11: 2})
    container = TheoryCompiledTarget(native, abstr, [absent, a], env=mgr.env)
    path = tmp_path / "artifact"
    container.save(path)
    return path, container


def test_sparse_roundtrip_and_environment(artifact):
    path, original = artifact
    fresh = Environment()
    loaded = TheoryCompiledTarget.load(path, type(original.target), env=fresh)
    assert loaded.env is fresh
    assert list(loaded.abstr.id_to_atom) == [3, 7, 11]
    assert [loaded.abstr.get_id(a) for a in loaded.projection_atoms] == [11, 3]
    assert loaded.to_pysmt() is fresh.formula_manager.Symbol("a") or loaded.to_pysmt().simplify().is_symbol()
    assert loaded.abstr.get_atom(3) is fresh.formula_manager.Symbol("a")
    if isinstance(original.target, BddCompiledTarget):
        assert loaded.target.manager.var_levels == original.target.manager.var_levels
    if isinstance(original.target, SddCompiledTarget):
        assert "circuit.vtree" in read_json(path / "metadata.json")["files"]
        second = path.parent / "second"
        loaded.save(second)
        assert (second / "circuit.vtree").read_bytes() == (path / "circuit.vtree").read_bytes()
    if isinstance(original.target, D4CompiledTarget):
        assert loaded.target.remapping == {3: 1, 11: 2}


@pytest.mark.parametrize("value", [False, True])
@pytest.mark.parametrize("rep", ["obdd", "sdd", "ddnnf"])
def test_constants(tmp_path, mgr, value, rep):
    if rep == "obdd":
        manager = BDD()
        manager.declare("b1")
        native = BddCompiledTarget(manager.true if value else manager.false, manager)
    elif rep == "sdd":
        manager = SddManager(var_count=1)
        native = SddCompiledTarget(manager.true() if value else manager.false(), manager)
    else:
        native = D4CompiledTarget("t 1\n" if value else "f 1\n", 0)
    target = TheoryCompiledTarget(native, Abstractor(), [], mgr.env)
    path = tmp_path / "constant"
    target.save(path)
    assert TheoryCompiledTarget.load(path, type(native), env=mgr.env).to_pysmt() is mgr.Bool(value)


@pytest.mark.parametrize("container_load", [False, True])
@pytest.mark.parametrize("version", [999, True])
def test_unsupported_schema_version(artifact, version, container_load):
    path, original = artifact
    data = read_json(path / "metadata.json")
    data["schema_version"] = version
    (path / "metadata.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="schema version"):
        if container_load:
            TheoryCompiledTarget.load(path, type(original.target))
        else:
            type(original.target).load(path)


@pytest.mark.parametrize("container_load", [False, True])
def test_unversioned_requires_migration(artifact, container_load):
    path, original = artifact
    data = read_json(path / "metadata.json")
    del data["schema_version"]
    (path / "metadata.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="migration"):
        if container_load:
            TheoryCompiledTarget.load(path, type(original.target))
        else:
            type(original.target).load(path)


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


def test_sdd_minimized_vtree_roundtrip(tmp_path, mgr):
    manager = SddManager.from_vtree(Vtree(var_count=5, vtree_type="right"))
    manager.auto_gc_and_minimize_off()
    root = (manager.literal(1) & manager.literal(5)) | (manager.literal(2) & manager.literal(4))
    root.ref()
    manager.minimize()
    target = SddCompiledTarget(root, manager)
    path = tmp_path / "minimized"
    target.save(path)
    loaded = SddCompiledTarget.load(path)
    abstr = Abstractor({i: mgr.Symbol(f"v{i}") for i in range(1, 6)})
    with mgr.env.factory.Solver() as solver:
        solver.add_assertion(mgr.Not(mgr.Iff(target.to_pysmt(abstr, mgr), loaded.to_pysmt(abstr, mgr))))
        assert not solver.solve()
    root.deref()


def test_obdd_empty_manager_constant(tmp_path):
    manager = BDD()
    path = tmp_path / "empty"
    BddCompiledTarget(manager.false, manager).save(path)
    loaded = BddCompiledTarget.load(path)
    assert loaded.root == loaded.manager.false
    assert loaded.manager.vars == set()


def test_d4_sparse_node_ids(tmp_path):
    target = D4CompiledTarget("o 1 0\nt 1000 0\n1 1000 1 0\n", 1, {7: 1})
    path = tmp_path / "sparse"
    target.save(path)
    assert D4CompiledTarget.load(path).nnf_text == target.nnf_text


@pytest.mark.parametrize("payload", ["not a graph\n", "o 1 0\n1 1 1 0\n"])
def test_d4_payload_is_preserved_without_graph_validation(tmp_path, payload):
    target = D4CompiledTarget(payload, 1, {3: 1})
    target.save(tmp_path / "target")
    assert D4CompiledTarget.load(tmp_path / "target").nnf_text == payload


def test_save_does_not_reload_state(tmp_path, monkeypatch, mgr):
    def forbidden(*args, **kwargs):
        pytest.fail("Saving must not reconstruct saved state")

    monkeypatch.setattr(D4CompiledTarget, "load", forbidden)
    monkeypatch.setattr(Abstractor, "from_dict", forbidden)
    target = TheoryCompiledTarget(D4CompiledTarget("t 1\n", 0), Abstractor(), [], mgr.env)
    target.save(tmp_path / "target")


def test_missing_abstraction_propagates(tmp_path, mgr):
    path = tmp_path / "target"
    TheoryCompiledTarget(D4CompiledTarget("t 1\n", 0), Abstractor(), [], mgr.env).save(path)
    (path / "abstraction.json").unlink()
    with pytest.raises(FileNotFoundError):
        TheoryCompiledTarget.load(path, D4CompiledTarget)


def test_missing_d4_payload_propagates(tmp_path):
    path = tmp_path / "target"
    D4CompiledTarget("t 1\n", 0).save(path)
    (path / "circuit.nnf").unlink()
    with pytest.raises(FileNotFoundError):
        D4CompiledTarget.load(path)


@pytest.mark.parametrize("legacy_flag", [False, True])
def test_missing_sdd_vtree_requires_recompilation(tmp_path, legacy_flag):
    manager = SddManager(var_count=1)
    path = tmp_path / "target"
    SddCompiledTarget(manager.literal(1), manager).save(path)
    (path / "circuit.vtree").unlink()
    if legacy_flag:
        data = read_json(path / "metadata.json")
        data["legacy_missing_vtree"] = True
        data["files"].remove("circuit.vtree")
        (path / "metadata.json").write_text(json.dumps(data))
    with pytest.raises(FileNotFoundError, match="circuit.vtree"):
        SddCompiledTarget.load(path)


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
    fresh = Environment()
    loaded = assert_type(TheoryCompiledTarget.load(path, LiteralTarget, env=fresh), TheoryCompiledTarget[LiteralTarget])
    assert isinstance(loaded.target, LiteralTarget)
    assert isinstance(loaded.target, PropCompiledTarget)
    assert loaded.target.atom_id == 7
    assert loaded.env is fresh
    assert loaded.to_pysmt() is fresh.formula_manager.Symbol("atom")
    assert [loaded.abstr.get_id(a) for a in loaded.projection_atoms] == [11, 7]
    assert loaded.dag_size() == DagSize(1, 0)
    assert read_json(path / "metadata.json") == {
        "schema_version": 1,
        "representation": "literal",
        "codec": "integer-text",
        "files": ["literal.txt", "abstraction.json"],
    }


def test_load_requires_target_type(tmp_path):
    with pytest.raises(TypeError, match="target_type"):
        TheoryCompiledTarget.load(tmp_path)


def test_backend_exception_propagates(tmp_path, monkeypatch):
    path = tmp_path / "custom"
    LiteralTarget(7).save(path)
    error = RuntimeError("backend failure")

    def fail(directory):
        raise error

    monkeypatch.setattr(LiteralTarget, "load", fail)
    with pytest.raises(RuntimeError) as caught:
        TheoryCompiledTarget.load(path, LiteralTarget)
    assert caught.value is error


@pytest.mark.parametrize("version", [None, True, 999])
def test_container_delegates_validation_to_backend(tmp_path, monkeypatch, mgr, version):
    path = tmp_path / "custom"
    native = LiteralTarget(7)
    TheoryCompiledTarget(native, Abstractor({7: mgr.Symbol("a")}), [], mgr.env).save(path)
    data = read_json(path / "metadata.json")
    if version is None:
        del data["schema_version"]
    else:
        data["schema_version"] = version
    (path / "metadata.json").write_text(json.dumps(data))
    calls = []

    def load(directory):
        calls.append(directory)
        return native

    monkeypatch.setattr(LiteralTarget, "load", load)
    assert TheoryCompiledTarget.load(path, LiteralTarget).target is native
    assert calls == [path]


def test_container_reads_metadata_once(artifact, monkeypatch):
    path, original = artifact
    read_text = Path.read_text
    reads = []

    def track_reads(file, *args, **kwargs):
        if file == path / "metadata.json":
            reads.append(file)
        return read_text(file, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", track_reads)
    TheoryCompiledTarget.load(path, type(original.target))
    assert reads == [path / "metadata.json"]
