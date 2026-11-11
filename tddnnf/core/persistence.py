"""Versioned native codecs shared by standalone targets and theory containers."""

from __future__ import annotations

import json
import re
import tempfile
from array import array
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1
CODECS = {"obdd": "dddmp-2.0", "sdd": "pysdd", "ddnnf": "d4"}
PAYLOADS = {"obdd": "circuit.dddmp", "sdd": "circuit.sdd", "ddnnf": "circuit.nnf"}


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"Expected integer >= {minimum}, got {value!r}")
    return value


def read_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Invalid JSON constant: {value}")

    value = json.loads(Path(path).read_text(), object_pairs_hook=unique_object, parse_constant=invalid_constant)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


@contextmanager
def publication(directory):
    """Validate in a sibling directory; an existing destination is never replaced."""
    directory = Path(directory)
    if directory.exists() or directory.is_symlink():
        raise FileExistsError(directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{directory.name}-", dir=directory.parent) as tmp:
        stage = Path(tmp) / "artifact"
        stage.mkdir()
        yield stage
        if directory.exists() or directory.is_symlink():
            raise FileExistsError(directory)
        stage.rename(directory)


def metadata(directory):
    data = read_json(Path(directory) / "metadata.json")
    if "schema_version" not in data:
        raise ValueError("Unversioned artifact requires migration")
    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported persistence schema version")
    rep = data.get("representation")
    if not isinstance(rep, str) or rep not in CODECS or data.get("codec") != CODECS[rep]:
        raise ValueError("Unsupported representation or codec")
    integer(data.get("var_count"))
    if "legacy_missing_vtree" in data and (rep != "sdd" or data["legacy_missing_vtree"] is not True):
        raise ValueError("Invalid legacy missing-vtree exception")
    files = data.get("files")
    if not isinstance(files, list) or any(not isinstance(name, str) for name in files) or len(files) != len(set(files)):
        raise ValueError("Invalid declared files")
    required = {PAYLOADS[rep]}
    if rep == "sdd":
        if data.get("legacy_missing_vtree") is True:
            if "circuit.vtree" in files:
                raise ValueError("Legacy missing-vtree exception conflicts with saved vtree")
        else:
            required.add("circuit.vtree")
    if not required <= set(files):
        raise ValueError("Missing required file declaration")
    for name in files:
        if not isinstance(name, str) or Path(name).name != name or name in (".", ".."):
            raise ValueError("Invalid declared filename")
        path = Path(directory) / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Missing or unsafe declared file: {name}")
    return data


def dddmp_info(path):
    text = Path(path).read_text()
    if not text.isascii():
        raise ValueError("DDDMP records must be ASCII")
    lines = text.splitlines()
    header = {}
    nodes = []
    in_nodes = False
    ended = False
    started = False
    for line in lines:
        parts = line.split()
        if not parts:
            continue
        if ended:
            raise ValueError("Trailing DDDMP records")
        if parts[0] == ".nodes":
            if started:
                raise ValueError("Duplicate DDDMP nodes section")
            started = True
            in_nodes = True
        elif parts[0] == ".end":
            if not in_nodes:
                raise ValueError("Misplaced DDDMP end")
            ended = True
            in_nodes = False
        elif in_nodes:
            nodes.append(parts)
        elif parts[0].startswith("."):
            if parts[0] in header:
                raise ValueError("Duplicate DDDMP header")
            header[parts[0]] = parts[1:]
        else:
            raise ValueError("Malformed DDDMP")
    if header.get(".ver") != ["DDDMP-2.0"] or header.get(".mode") != ["A"] or header.get(".varinfo") != ["3"]:
        raise ValueError("Unsupported DDDMP format")
    order = header.get(".orderedvarnames", [])
    if len(set(order)) != len(order) or any(not re.fullmatch(r"b[1-9][0-9]*", n) for n in order):
        raise ValueError("Unrecoverable DDDMP variable order")
    if header.get(".nvars") != [str(len(order))] or header.get(".nroots") != ["1"]:
        raise ValueError("Invalid DDDMP variable/root count")
    support = header.get(".suppvarnames", [])
    if not set(support) <= set(order) or header.get(".nsuppvars") != [str(len(support))]:
        raise ValueError("Invalid DDDMP support")
    ids = [int(i) for i in header.get(".ids", [])]
    permids = [int(i) for i in header.get(".permids", [])]
    if (
        len(ids) != len(support)
        or len(set(ids)) != len(ids)
        or any(i < 0 or i >= len(order) for i in ids)
        or permids != [order.index(name) for name in support]
    ):
        raise ValueError("Invalid DDDMP IDs/permutation")
    ranks = {name: rank for rank, name in enumerate(sorted(support, key=order.index))}
    if header.get(".nnodes") != [str(len(nodes))] or not ended:
        raise ValueError("Truncated DDDMP")
    seen = set()
    levels = {}
    used_vars = set()
    for parts in nodes:
        if len(parts) != 5:
            raise ValueError("Invalid DDDMP node")
        nid, level, high, low = (int(parts[i]) for i in (0, 2, 3, 4))
        if nid != len(seen) + 1:
            raise ValueError("Invalid DDDMP node ID")
        if parts[1] == "T":
            if nid != 1 or level != 1 or high != 0 or low != 0:
                raise ValueError("Invalid DDDMP terminal")
        elif (
            parts[1] not in support
            or high not in seen
            or abs(low) not in seen
            or level != ranks.get(parts[1])
            or level >= levels[high]
            or level >= levels[abs(low)]
        ):
            raise ValueError("Invalid DDDMP reference")
        else:
            used_vars.add(parts[1])
        levels[nid] = len(support) if parts[1] == "T" else level
        seen.add(nid)
    if used_vars != set(support) or len(support) != len(set(support)):
        raise ValueError("DDDMP support disagrees with nodes")
    roots = header.get(".rootids", [])
    if len(roots) != 1 or abs(int(roots[0])) not in seen:
        raise ValueError("Invalid DDDMP root")
    return order, {int(n[1:]) for n in support}


def records(path, header):
    lines = []
    for line in Path(path).read_text().split("\n"):
        if line.startswith("c"):
            continue
        if not line.isascii():
            raise ValueError(f"{header} records must be ASCII")
        if line.strip():
            lines.append(line.split())
    if not lines or len(lines[0]) != 2 or lines[0][0] != header or int(lines[0][1]) != len(lines) - 1:
        raise ValueError(f"Invalid {header} header/count")
    return lines[1:]


def sdd_info(directory, data, tree_path=None):
    count = data["var_count"]
    if count < 1:
        raise ValueError("SDD requires at least one native variable")
    tree = {}
    positions = {}
    branches = {}
    if tree_path is not None or not data.get("legacy_missing_vtree"):
        leaves = set()
        used = set()
        for p in records(tree_path or Path(directory) / "circuit.vtree", "vtree"):
            nid = int(p[1])
            if nid < 0 or nid in tree:
                raise ValueError("Invalid vtree node ID")
            if p[0] == "L" and len(p) == 3:
                var = int(p[2])
                if var < 1 or var > count or var in leaves:
                    raise ValueError("Invalid vtree variable")
                leaves.add(var)
                tree[nid] = {var}
                positions[nid] = (nid, nid)
            elif p[0] == "I" and len(p) == 4:
                left, right = map(int, p[2:])
                if left not in tree or right not in tree or left == right or {left, right} & used:
                    raise ValueError("Invalid vtree children")
                if positions[left][1] >= nid or positions[right][0] <= nid:
                    raise ValueError("Vtree IDs must be inorder positions")
                used.update((left, right))
                positions[nid] = (positions[left][0], positions[right][1])
                tree[nid] = tree[left] | tree[right]
                branches[nid] = (left, right)
            else:
                raise ValueError("Invalid vtree record")
        if leaves != set(range(1, count + 1)) or set(tree) != set(range(2 * count - 1)) or len(used) != len(tree) - 1:
            raise ValueError("Incomplete vtree")
    support = set()
    seen = set()
    scopes = {}
    for p in records(Path(directory) / "circuit.sdd", "sdd"):
        nid = int(p[1])
        if nid < 0 or nid in seen:
            raise ValueError("Invalid SDD node ID")
        if p[0] in ("T", "F") and len(p) == 2:
            scopes[nid] = set()
        elif p[0] == "L" and len(p) == 4:
            vt, lit = map(int, p[2:])
            if not 1 <= abs(lit) <= count or (tree and tree.get(vt) != {abs(lit)}):
                raise ValueError("Invalid SDD literal/vtree")
            support.add(abs(lit))
            scopes[nid] = {abs(lit)}
        elif p[0] == "D" and len(p) >= 4:
            vt, n = map(int, p[2:4])
            if n < 1 or len(p) != 4 + 2 * n or (tree and (vt not in tree or len(tree[vt]) < 2)):
                raise ValueError("Invalid SDD decomposition")
            if any(int(child) not in seen for child in p[4:]):
                raise ValueError("Invalid SDD child")
            if tree:
                left, right = branches[vt]
                for prime, sub in zip(p[4::2], p[5::2]):
                    if not scopes[int(prime)] <= tree[left] or not scopes[int(sub)] <= tree[right]:
                        raise ValueError("SDD child incompatible with vtree")
            scopes[nid] = set().union(*(scopes[int(child)] for child in p[4:]))
        else:
            raise ValueError("Invalid SDD record")
        seen.add(nid)
    if not seen or seen != set(range(len(seen))):
        raise ValueError("SDD node IDs must cover 0..node_count-1")
    return support


def d4_info(path, count):
    with Path(path).open() as source:
        return _d4_records(source, count)


def _d4_records(source, count):
    # Native d4 IDs are normally dense; packed arrays keep large graphs practical.
    kinds = bytearray()
    sparse = None
    sources, destinations = array("q"), array("q")
    support = set()
    for line in source:
        p = line.split()
        if not p or p[0] == "c":
            continue
        if p[0] in ("a", "o", "t", "f"):
            if len(p) not in (2, 3) or (len(p) == 3 and p[2] != "0"):
                raise ValueError("Invalid d4 node")
            nid = int(p[1])
            if sparse is None and nid != len(kinds) + 1:
                sparse = {i + 1: i for i in range(len(kinds))}
            if nid <= 0 or (sparse is not None and nid in sparse):
                raise ValueError("Invalid d4 node ID")
            if sparse is not None:
                sparse[nid] = len(kinds)
            kinds.append({"a": 0, "o": 1, "t": 2, "f": 3}[p[0]])
        else:
            values = list(map(int, p))
            if (
                len(values) < 3
                or values[-1] != 0
                or any(not 1 <= abs(lit) <= count for lit in values[2:-1])
                or any(not 1 <= endpoint < 2**63 for endpoint in values[:2])
            ):
                raise ValueError("Invalid d4 edge/literal")
            if (sparse is None and values[0] > len(kinds)) or (sparse is not None and values[0] not in sparse):
                raise ValueError("d4 edge source must be declared before its edges")
            sources.append(values[0])
            destinations.append(values[1])
            support.update(abs(lit) for lit in values[2:-1])
    if not kinds or (sparse is not None and 1 not in sparse):
        raise ValueError("Missing d4 root")
    heads = array("q", [-1]) * len(kinds)
    degrees = array("q", [0]) * len(kinds)
    for edge in range(len(sources)):
        src, dst = sources[edge], destinations[edge]
        if sparse is not None:
            src, dst = sparse.get(src, -1), sparse.get(dst, -1)
        else:
            src, dst = src - 1, dst - 1
        if not 0 <= src < len(kinds) or not 0 <= dst < len(kinds) or kinds[src] >= 2:
            raise ValueError("Invalid d4 endpoint")
        destinations[edge] = dst
        sources[edge] = heads[src]
        heads[src] = edge
        degrees[dst] += 1
    # Kahn's algorithm avoids recursion limits on large circuits.
    stack = [nid for nid in range(len(kinds)) if degrees[nid] == 0]
    visited = 0
    while stack:
        nid = stack.pop()
        visited += 1
        edge = heads[nid]
        while edge != -1:
            ref = destinations[edge]
            degrees[ref] -= 1
            if degrees[ref] == 0:
                stack.append(ref)
            edge = sources[edge]
    if visited != len(kinds):
        raise ValueError("Cyclic d4 graph")
    return support


def validate_native(directory, data):
    rep = data["representation"]
    count = data["var_count"]
    if rep == "obdd":
        order, support = dddmp_info(Path(directory) / PAYLOADS[rep])
        if order != data.get("variable_order") or len(order) != count:
            raise ValueError("OBDD order disagrees with payload")
        return support
    if rep == "sdd":
        if data.get("legacy_missing_vtree") is True:
            from pysdd.sdd import SddManager

            if count < 1:
                raise ValueError("SDD requires at least one native variable")
            with tempfile.TemporaryDirectory() as tmp:
                tree_path = Path(tmp) / "balanced.vtree"
                mgr = SddManager(var_count=count)
                mgr.vtree().save(str(tree_path).encode())
                return sdd_info(directory, data, tree_path)
        return sdd_info(directory, data)
    remap = data.get("remapping")
    if not isinstance(remap, dict):
        raise ValueError("Missing d4 remapping")
    for key, value in remap.items():
        if not re.fullmatch(r"[1-9][0-9]*", key):
            raise ValueError("Invalid abstraction remapping ID")
        integer(value, 1)
    if set(remap.values()) != set(range(1, count + 1)) or len(remap) != count:
        raise ValueError("d4 remapping must be a bijection onto native IDs")
    support = d4_info(Path(directory) / PAYLOADS[rep], count)
    inverse = {v: int(k) for k, v in remap.items()}
    return {inverse[i] for i in support}


def write_native(target, directory):
    from tddnnf.compilers.cudd import BddCompiledTarget
    from tddnnf.compilers.d4 import D4CompiledTarget
    from tddnnf.compilers.pysdd import SddCompiledTarget

    if isinstance(target, BddCompiledTarget):
        rep = "obdd"
        order = sorted(target.manager.vars, key=target.manager.level_of_var)
        target.manager.dump(str(directory / PAYLOADS[rep]), [target.root])
        extra = {"var_count": len(order), "variable_order": order}
    elif isinstance(target, SddCompiledTarget):
        rep = "sdd"
        target.manager.save(str(directory / PAYLOADS[rep]).encode(), target.root)
        if not target._legacy_missing_vtree:
            target.manager.vtree().save(str(directory / "circuit.vtree").encode())
        extra = {"var_count": target.manager.var_count()}
    elif isinstance(target, D4CompiledTarget):
        rep = "ddnnf"
        (directory / PAYLOADS[rep]).write_text(target.nnf_text)
        extra = {"var_count": target.var_count, "remapping": {str(k): v for k, v in target.remapping.items()}}
    else:
        raise TypeError(f"Unsupported target: {type(target)}")
    legacy_vtree = rep == "sdd" and target._legacy_missing_vtree
    if legacy_vtree:
        extra["legacy_missing_vtree"] = True
    files = [PAYLOADS[rep]] + (["circuit.vtree"] if rep == "sdd" and not legacy_vtree else [])
    data = {"schema_version": SCHEMA_VERSION, "representation": rep, "codec": CODECS[rep], "files": files, **extra}
    (directory / "metadata.json").write_text(json.dumps(data, indent=2))


def _load_sdd(directory, manager):
    # Build through checked operations: PySDD's raw reader trusts unsafe partition invariants.
    nodes = {}
    for parts in records(Path(directory) / "circuit.sdd", "sdd"):
        kind, nid = parts[0], int(parts[1])
        if kind == "T":
            root = manager.true()
        elif kind == "F":
            root = manager.false()
        elif kind == "L":
            root = manager.literal(int(parts[3]))
        else:
            covered = manager.false()
            root = manager.false()
            subs = set()
            if int(parts[3]) < 2:
                raise ValueError("Untrimmed SDD decision")
            for prime_id, sub_id in zip(parts[4::2], parts[5::2]):
                prime, sub = nodes[int(prime_id)], nodes[int(sub_id)]
                if prime.is_true() or prime.is_false() or not (covered & prime).is_false():
                    raise ValueError("SDD primes must be nonconstant and disjoint")
                if sub.id in subs:
                    raise ValueError("SDD decision must be compressed")
                subs.add(sub.id)
                covered = covered | prime
                root = root | (prime & sub)
            if not covered.is_true():
                raise ValueError("SDD primes must be exhaustive")
        nodes[nid] = root
    return root


def load_native(directory, expected=None):
    from dd.cudd import BDD
    from pysdd.sdd import SddManager, Vtree

    from tddnnf.compilers.cudd import BddCompiledTarget
    from tddnnf.compilers.d4 import D4CompiledTarget
    from tddnnf.compilers.pysdd import SddCompiledTarget

    directory = Path(directory)
    data = metadata(directory)
    rep = data["representation"]
    classes = {"obdd": BddCompiledTarget, "sdd": SddCompiledTarget, "ddnnf": D4CompiledTarget}
    if expected is not None and classes[rep] is not expected:
        raise ValueError("Representation disagrees with requested target type")
    validate_native(directory, data)
    if rep == "obdd":
        mgr = BDD()
        mgr.configure(reordering=False)
        mgr.declare(*data["variable_order"])
        roots = mgr.load(str(directory / PAYLOADS[rep]))
        if len(roots) != 1:
            raise ValueError("Expected one OBDD root")
        mgr.reorder({name: level for level, name in enumerate(data["variable_order"])})
        return BddCompiledTarget(roots[0], mgr)
    if rep == "sdd":
        if data.get("legacy_missing_vtree") is True:
            mgr = SddManager(var_count=data["var_count"])
        else:
            tree = Vtree.from_file(str(directory / "circuit.vtree").encode())
            mgr = SddManager.from_vtree(tree)
        mgr.auto_gc_and_minimize_off()
        root = _load_sdd(directory, mgr)
        target = SddCompiledTarget(root, mgr)
        target._legacy_missing_vtree = data.get("legacy_missing_vtree") is True
        return target
    return D4CompiledTarget(
        (directory / PAYLOADS[rep]).read_text(), data["var_count"], {int(k): v for k, v in data["remapping"].items()}
    )


def save_native(target, directory):
    with publication(directory) as stage:
        write_native(target, stage)
        load_native(stage, type(target))
