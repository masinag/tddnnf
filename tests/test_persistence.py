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


@pytest.mark.parametrize(
    "mutation", ["duplicate_ids", "duplicate_projection", "unknown_projection", "support", "conflict"]
)
def test_bad_abstraction(artifact, mutation):
    path, _ = artifact
    payload = read_json(path / "abstraction.json")
    if mutation == "duplicate_ids":
        payload["abstraction"] = dict.fromkeys(payload["abstraction"], 3)
    elif mutation == "duplicate_projection":
        payload["projection_atom_ids"] = [3, 3]
    elif mutation == "unknown_projection":
        payload["projection_atom_ids"] = [100]
    elif mutation == "support":
        payload["projection_atom_ids"] = [11]
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


def test_failure_cleanup(tmp_path):
    target = D4CompiledTarget("o 1 0\n1 1 1 0\n", 1, {3: 1})
    with pytest.raises(ValueError, match="Cyclic"):
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


@pytest.mark.parametrize(
    "rep,payload",
    [
        ("obdd", ".ver DDDMP-2.0\n.mode A\n.nodes\n1 b1 0 9 9\n.end\n"),
        ("sdd", "sdd 1\nD 0 0 1 8 9\n"),
        ("ddnnf", "o 1 0\n1 9 1 0\n"),
    ],
)
def test_corrupt_payload(tmp_path, rep, payload):
    from tddnnf.core.persistence import CODECS, PAYLOADS, load_native

    path = tmp_path / "bad"
    path.mkdir()
    data = dict(schema_version=1, representation=rep, codec=CODECS[rep], var_count=1, files=[PAYLOADS[rep]])
    if rep == "sdd":
        data["legacy_missing_vtree"] = True
    if rep == "ddnnf":
        data["remapping"] = {"3": 1}
    (path / "metadata.json").write_text(json.dumps(data))
    (path / PAYLOADS[rep]).write_text(payload)
    with pytest.raises(ValueError):
        load_native(path)


@pytest.mark.parametrize("mutation", ["node_id", "permutation", "level", "varinfo"])
def test_dddmp_native_crash_regressions(tmp_path, mutation):
    manager = BDD()
    manager.declare("b1")
    path = tmp_path / "bdd"
    BddCompiledTarget(manager.var("b1"), manager).save(path)
    payload = path / "circuit.dddmp"
    text = payload.read_text()
    if mutation == "node_id":
        text = text.replace("2 b1", "1000000 b1").replace(".rootids 2", ".rootids 1000000")
    elif mutation == "permutation":
        text = text.replace(".permids 0", ".permids 1000000")
    elif mutation == "level":
        text = text.replace("2 b1 0", "2 b1 1000000")
    else:
        text = text.replace(".varinfo 3", ".varinfo 0")
    payload.write_text(text)
    with pytest.raises(ValueError):
        BddCompiledTarget.load(path)


@pytest.mark.parametrize("mutation", ["sdd_id", "vtree_id", "vtree_order"])
def test_sdd_native_crash_regressions(tmp_path, mutation):
    manager = SddManager(var_count=2)
    path = tmp_path / "sdd"
    SddCompiledTarget(manager.literal(1), manager).save(path)
    if mutation == "sdd_id":
        (path / "circuit.sdd").write_text("sdd 1\nL 1000000 0 1\n")
    elif mutation == "vtree_id":
        (path / "circuit.vtree").write_text("vtree 3\nL 1000000 1\nL 2 2\nI 1 1000000 2\n")
    else:
        (path / "circuit.vtree").write_text("vtree 3\nL 2 1\nL 0 2\nI 1 2 0\n")
    with pytest.raises(ValueError):
        SddCompiledTarget.load(path)


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


@pytest.mark.parametrize(
    "payload",
    [
        "sdd 3\nF 0\nT 1\nD 2 1 1 0 1\n",
        "sdd 3\nT 0\nF 1\nD 2 1 2 0 0 0 1\n",
        "sdd 4\nL 0 0 1\nT 1\nF 2\nD 3 1 2 0 1 0 2\n",
    ],
)
def test_sdd_invalid_partitions(tmp_path, payload):
    manager = SddManager(var_count=2)
    path = tmp_path / "sdd"
    SddCompiledTarget(manager.literal(1), manager).save(path)
    (path / "circuit.sdd").write_text(payload)
    with pytest.raises(ValueError):
        SddCompiledTarget.load(path)


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


@pytest.mark.parametrize("replacement", ["L ２ 2", "L\u20032 2"])
def test_nonascii_vtree_tokens_rejected(tmp_path, replacement):
    manager = SddManager(var_count=2)
    path = tmp_path / "sdd"
    SddCompiledTarget(manager.literal(1), manager).save(path)
    tree = path / "circuit.vtree"
    tree.write_text(tree.read_text().replace("L 2 2", replacement))
    with pytest.raises(ValueError, match="ASCII"):
        SddCompiledTarget.load(path)
