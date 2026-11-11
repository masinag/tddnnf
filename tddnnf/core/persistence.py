"""Backend-independent metadata and artifact saving helpers."""

from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1


def read_json(path):
    return json.loads(Path(path).read_text())


@contextmanager
def saving_to(directory):
    """Write to a temporary directory, rename on success, and clean up on failure.

    An existing destination is never replaced.
    """
    directory = Path(directory)
    if directory.exists() or directory.is_symlink():
        raise FileExistsError(directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{directory.name}-", dir=directory.parent) as tmp:
        temporary_directory = Path(tmp) / "artifact"
        yield temporary_directory
        if directory.exists() or directory.is_symlink():
            raise FileExistsError(directory)
        temporary_directory.rename(directory)


def read_metadata(directory):
    data = read_json(Path(directory) / "metadata.json")
    if "schema_version" not in data:
        raise ValueError("Unversioned artifact requires migration")
    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported persistence schema version")
    return data


def write_metadata(directory, representation, *, codec, files, **extra):
    data = {
        "schema_version": SCHEMA_VERSION,
        "representation": representation,
        "codec": codec,
        "files": files,
        **extra,
    }
    (Path(directory) / "metadata.json").write_text(json.dumps(data, indent=2))
