import json
from pathlib import Path

import pytest

from tddnnf.core.persistence import read_metadata, saving_to, write_metadata


def test_metadata_round_trip(tmp_path: Path) -> None:
    write_metadata(tmp_path, "test-target", codec="json", files=["payload.json"], label="example")

    assert read_metadata(tmp_path) == {
        "schema_version": 1,
        "representation": "test-target",
        "codec": "json",
        "files": ["payload.json"],
        "label": "example",
    }


def test_missing_schema_version_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "metadata.json").write_text(json.dumps({"representation": "test-target"}))

    with pytest.raises(ValueError):
        read_metadata(tmp_path)


@pytest.mark.parametrize("version", [0, 2, "1", True, False, 1.0])
def test_unsupported_schema_version_is_rejected(tmp_path: Path, version) -> None:
    (tmp_path / "metadata.json").write_text(json.dumps({"schema_version": version}))

    with pytest.raises(ValueError):
        read_metadata(tmp_path)


def test_missing_metadata_propagates_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_metadata(tmp_path)


def test_malformed_metadata_propagates_json_decode_error(tmp_path: Path) -> None:
    (tmp_path / "metadata.json").write_text("{")

    with pytest.raises(json.JSONDecodeError):
        read_metadata(tmp_path)


def test_saving_publishes_payload_after_context_exit(tmp_path: Path) -> None:
    destination = tmp_path / "target"

    with saving_to(destination) as temporary:
        temporary.mkdir()
        (temporary / "payload.json").write_text(json.dumps({"value": 7}))
        assert not destination.exists()

    assert json.loads((destination / "payload.json").read_text()) == {"value": 7}
    assert list(tmp_path.iterdir()) == [destination]


def test_saving_propagates_exception_and_cleans_up(tmp_path: Path) -> None:
    destination = tmp_path / "target"
    error = RuntimeError("save failed")

    with pytest.raises(RuntimeError) as caught:
        with saving_to(destination) as temporary:
            temporary.mkdir()
            (temporary / "payload.json").write_text(json.dumps({"value": 7}))
            raise error

    assert caught.value is error
    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []


def test_saving_refuses_existing_directory_and_preserves_contents(tmp_path: Path) -> None:
    destination = tmp_path / "target"
    destination.mkdir()
    payload = destination / "payload.json"
    original = json.dumps({"value": 7}).encode()
    payload.write_bytes(original)

    with pytest.raises(FileExistsError):
        with saving_to(destination):
            pytest.fail("saving entered an existing destination")

    assert payload.read_bytes() == original
    assert list(destination.iterdir()) == [payload]
    assert list(tmp_path.iterdir()) == [destination]
