"""Backend-independent metadata and artifact publication helpers."""

from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1
CODECS = {"obdd": "dddmp-2.0", "sdd": "pysdd", "ddnnf": "d4"}
PAYLOADS = {"obdd": "circuit.dddmp", "sdd": "circuit.sdd", "ddnnf": "circuit.nnf"}


def read_json(path):
    return json.loads(Path(path).read_text())


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
