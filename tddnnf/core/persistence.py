"""Backend-independent metadata and artifact saving helpers."""

from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

SCHEMA_VERSION = 1


def read_json(path: Path):
    """Read a JSON file."""
    return json.loads(path.read_text())


@contextmanager
def saving_to(directory: Path) -> Generator[Path, Any, None]:
    """Stage an artifact in a temporary directory and move it to its destination on success.

    The temporary directory is created alongside the destination and cleaned up
    when the context exits. If the context exits without an exception, the staged
    artifact is renamed to the destination.

    Args:
        directory: Final destination path for the artifact.

    Yields:
        Path to the temporary location where the artifact should be created.

    Raises:
        FileExistsError: If the destination already exists, either when entering
            the context or immediately before moving the artifact.
    """
    if directory.exists() or directory.is_symlink():
        raise FileExistsError(directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{directory.name}-", dir=directory.parent) as tmp:
        temporary_directory = Path(tmp) / "artifact"
        yield temporary_directory
        if directory.exists() or directory.is_symlink():
            raise FileExistsError(directory)
        temporary_directory.rename(directory)


def read_metadata(directory: Path) -> dict[str, Any]:
    """Read and validate artifact metadata from a directory.

    Args:
        directory: Directory containing the metadata.json file.

    Returns:
        dict[str, Any]: The validated artifact metadata as a dictionary.

    Raises:
        FileNotFoundError: If the directory or metadata file does not exist.
        ValueError: If the metadata has an invalid format or unsupported schema version.
    """
    if not directory.exists():
        raise FileNotFoundError(f"directory {directory} does not exist")
    data_file = directory / "metadata.json"
    if not data_file.is_file():
        raise FileNotFoundError(f"file {data_file} does not exist")
    data = read_json(data_file)
    if type(data) is not dict:
        raise ValueError(f"expected dict type, got {type(data)}")
    if "schema_version" not in data:
        raise ValueError("Unversioned artifact requires migration")
    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported persistence schema version")
    return data


def write_metadata(directory: Path, representation: str, *, codec: str, files: list[str], **extra: Any) -> None:
    """Write artifact metadata to a metadata.json file in the given directory.

    Args:
        directory: Directory in which to write the metadata file.
        representation: KC language used to represent the artifact.
        codec: Format used to persist the artifact.
        files: List of artifact files in the directory.
        **extra: Additional metadata fields to include in the JSON file.
    """
    data = {
        "schema_version": SCHEMA_VERSION,
        "representation": representation,
        "codec": codec,
        "files": files,
        **extra,
    }
    (directory / "metadata.json").write_text(json.dumps(data, indent=2))
