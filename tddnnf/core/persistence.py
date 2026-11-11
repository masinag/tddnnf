"""Backend-independent metadata and artifact publication helpers."""

from __future__ import annotations

import json
import tempfile
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
    """Stage in a sibling directory; an existing destination is never replaced."""
    directory = Path(directory)
    if directory.exists() or directory.is_symlink():
        raise FileExistsError(directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{directory.name}-", dir=directory.parent) as tmp:
        stage = Path(tmp) / "artifact"
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


def write_metadata(directory, representation, **extra):
    files = [PAYLOADS[representation]]
    if representation == "sdd" and not extra.get("legacy_missing_vtree"):
        files.append("circuit.vtree")
    data = {
        "schema_version": SCHEMA_VERSION,
        "representation": representation,
        "codec": CODECS[representation],
        "files": files,
        **extra,
    }
    (Path(directory) / "metadata.json").write_text(json.dumps(data, indent=2))


def backend_metadata(directory, representation):
    data = metadata(directory)
    if data["representation"] != representation:
        raise ValueError("Representation disagrees with requested target type")
    return data
