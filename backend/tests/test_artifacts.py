"""Model artifact lifecycle contract tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.core.exceptions import ModelArtifactError
from ml.artifacts import get_active_model_dir, get_active_model_id, publish_model_package

REQUIRED_FILES = (
    "lstm_model.pth",
    "lightgbm_model.txt",
    "lightgbm_model.txt.meta.json",
    "lstm_scaler_x.joblib",
    "lstm_scaler_y.joblib",
)


def _write_complete_source(path: Path) -> None:
    path.mkdir(parents=True)
    for filename in REQUIRED_FILES:
        (path / filename).write_bytes(filename.encode("utf-8"))


def test_publish_model_package_writes_manifest_and_active_pointer(tmp_path):
    source = tmp_path / "source"
    versions = tmp_path / "versions"
    active = tmp_path / "active.json"
    _write_complete_source(source)

    result = publish_model_package(
        source_dir=source,
        versions_dir=versions,
        active_file=active,
        activate=True,
        data_version="sales-test",
    )

    assert get_active_model_id(active_file=active) == result["model_id"]
    assert get_active_model_dir(active_file=active, versions_dir=versions) == Path(result["model_dir"])
    manifest = json.loads((Path(result["model_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["files"]) == set(REQUIRED_FILES)
    assert manifest["data_version"] == "sales-test"
    assert all(len(checksum) == 64 for checksum in manifest["checksums"].values())


def test_publish_model_package_rejects_missing_artifact_without_changing_active(tmp_path):
    source = tmp_path / "source"
    versions = tmp_path / "versions"
    active = tmp_path / "active.json"
    _write_complete_source(source)
    first = publish_model_package(source_dir=source, versions_dir=versions, active_file=active)
    (source / "lstm_scaler_y.joblib").unlink()

    with pytest.raises(ModelArtifactError, match="lstm_scaler_y.joblib"):
        publish_model_package(source_dir=source, versions_dir=versions, active_file=active)

    assert get_active_model_id(active_file=active) == first["model_id"]
