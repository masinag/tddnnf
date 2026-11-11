import json

import pytest
from dd.cudd import BDD
from pysdd.sdd import SddManager, Vtree
from pysmt.environment import Environment

from tddnnf.compilers.cudd import BddCompiledTarget
from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.compilers.pysdd import SddCompiledTarget
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.persistence import read_json


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
    loaded = TheoryCompiledTarget.load(path, env=fresh)
    assert loaded.env is fresh
    assert list(loaded.abstr.id_to_atom) == [3, 7, 11]
    assert [loaded.abstr.get_id(a) for a in loaded.projection_atoms] == [11, 3]
    assert loaded.to_pysmt() is fresh.formula_manager.Symbol("a") or loaded.to_pysmt().simplify().is_symbol()
    assert loaded.abstr.get_atom(3) is fresh.formula_manager.Symbol("a")
    if isinstance(original.target, BddCompiledTarget):
        assert loaded.target.manager.var_levels == original.target.manager.var_levels
    if isinstance(original.target, SddCompiledTarget):
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
    assert TheoryCompiledTarget.load(path, env=mgr.env).to_pysmt() is mgr.Bool(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 999),
        ("schema_version", True),
        ("codec", "unknown"),
        ("representation", "unknown"),
        ("files", []),
        ("files", ["../outside"]),
        ("files", [None]),
        ("var_count", -1),
        ("var_count", True),
    ],
)
def test_bad_metadata(artifact, field, value):
    path, _ = artifact
    data = read_json(path / "metadata.json")
    data[field] = value
    (path / "metadata.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        TheoryCompiledTarget.load(path)


def test_unversioned_requires_migration(artifact):
    path, _ = artifact
    data = read_json(path / "metadata.json")
    del data["schema_version"]
    (path / "metadata.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="migration"):
        TheoryCompiledTarget.load(path)


@pytest.mark.parametrize("mutation", ["duplicate_ids", "duplicate_projection", "unknown_projection", "conflict"])
def test_bad_abstraction(artifact, mutation):
    path, _ = artifact
    payload = read_json(path / "abstraction.json")
    if mutation == "duplicate_ids":
        payload["abstraction"] = dict.fromkeys(payload["abstraction"], 3)
    elif mutation == "duplicate_projection":
        payload["projection_atom_ids"] = [3, 3]
    elif mutation == "unknown_projection":
        payload["projection_atom_ids"] = [100]
    else:
        payload["care_var_ids"] = [3]
    (path / "abstraction.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        TheoryCompiledTarget.load(path)


def test_overwrite_and_missing_file(artifact):
    path, original = artifact
    before = (path / "metadata.json").read_bytes()
    with pytest.raises(FileExistsError):
        original.save(path)
    assert (path / "metadata.json").read_bytes() == before
    name = read_json(path / "metadata.json")["files"][0]
    (path / name).unlink()
    with pytest.raises(ValueError, match="Missing"):
        TheoryCompiledTarget.load(path)


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


def test_d4_mapping_covers_absent_active_atoms(tmp_path, mgr):
    a, absent = mgr.Symbol("a"), mgr.Symbol("absent")
    native = D4CompiledTarget("o 1 0\nt 2 0\n1 2 1 0\n", 1, {3: 1})
    target = TheoryCompiledTarget(native, Abstractor({3: a, 7: absent}), [a, absent], mgr.env)
    with pytest.raises(ValueError, match="cover"):
        target.save(tmp_path / "bad")
    assert not list(tmp_path.iterdir())


def test_obdd_empty_manager_constant(tmp_path):
    manager = BDD()
    path = tmp_path / "empty"
    BddCompiledTarget(manager.false, manager).save(path)
    loaded = BddCompiledTarget.load(path)
    assert loaded.root == loaded.manager.false
    assert loaded.manager.vars == set()


def test_d4_zero_count_mapping_exception_requires_canonical_constant(tmp_path, mgr):
    atom = mgr.Symbol("a")
    native = D4CompiledTarget("o 1 0\nt 2 0\n1 2 0\n", 0)
    target = TheoryCompiledTarget(native, Abstractor({3: atom}), [atom], mgr.env)
    with pytest.raises(ValueError, match="cover"):
        target.save(tmp_path / "bad")


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


@pytest.mark.parametrize("order", [None, ["b3", "b3"], ["invalid"], [True], []])
def test_bad_obdd_order(tmp_path, order):
    manager = BDD()
    manager.declare("b3")
    path = tmp_path / "bdd"
    BddCompiledTarget(manager.var("b3"), manager).save(path)
    data = read_json(path / "metadata.json")
    data["variable_order"] = order
    (path / "metadata.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="order"):
        BddCompiledTarget.load(path)


@pytest.mark.parametrize("remapping", [None, {"0": 1}, {"3": True}, {"3": 2}, {"3": 1, "7": 1}])
def test_bad_d4_mapping(tmp_path, remapping):
    path = tmp_path / "d4"
    D4CompiledTarget("t 1\n", 1, {3: 1}).save(path)
    data = read_json(path / "metadata.json")
    data["remapping"] = remapping
    (path / "metadata.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        D4CompiledTarget.load(path)


def test_save_does_not_reload_native_payload(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Saving must not reload a native payload")

    monkeypatch.setattr(D4CompiledTarget, "load", forbidden)
    D4CompiledTarget("t 1\n", 0).save(tmp_path / "target")
