"""Model artifact lifecycle contract tests."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from app.core.exceptions import ModelArtifactError
from ml.artifacts import get_active_model_dir, get_active_model_id, publish_model_package

REQUIRED_FILES = (
    "lstm_model.pth",
    "lightgbm_model.txt",
    "lightgbm_model.txt.meta.json",
    "lstm_scaler_x.json",
    "lstm_scaler_y.json",
    "category_encoder.json",
    "feature_schema.json",
    "model_selection.json",
    "evaluation_report.json",
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
    assert stat.S_IMODE(Path(result["model_dir"]).stat().st_mode) & 0o755 == 0o755
    manifest = json.loads((Path(result["model_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["files"]) == set(REQUIRED_FILES)
    assert manifest["data_version"] == "sales-test"
    assert all(len(checksum) == 64 for checksum in manifest["checksums"].values())


def test_active_model_pointer_is_readable_by_runtime_users(tmp_path):
    source = tmp_path / "source"
    versions = tmp_path / "versions"
    active = tmp_path / "active.json"
    _write_complete_source(source)

    publish_model_package(source_dir=source, versions_dir=versions, active_file=active)

    assert stat.S_IMODE(active.stat().st_mode) & 0o444 == 0o444


def test_publish_model_package_rejects_missing_artifact_without_changing_active(tmp_path):
    source = tmp_path / "source"
    versions = tmp_path / "versions"
    active = tmp_path / "active.json"
    _write_complete_source(source)
    first = publish_model_package(source_dir=source, versions_dir=versions, active_file=active)
    (source / "lstm_scaler_y.json").unlink()

    with pytest.raises(ModelArtifactError, match="lstm_scaler_y.json"):
        publish_model_package(source_dir=source, versions_dir=versions, active_file=active)

    assert get_active_model_id(active_file=active) == first["model_id"]


def test_active_model_rejects_tampered_package(tmp_path):
    source = tmp_path / "source"
    versions = tmp_path / "versions"
    active = tmp_path / "active.json"
    _write_complete_source(source)
    result = publish_model_package(source_dir=source, versions_dir=versions, active_file=active)
    (Path(result["model_dir"]) / "lstm_model.pth").write_bytes(b"tampered")

    with pytest.raises(ModelArtifactError, match="校验失败"):
        get_active_model_dir(active_file=active, versions_dir=versions)


def test_active_pointer_survives_interrupted_activation_and_fresh_process(tmp_path, monkeypatch):
    import ml.artifacts as artifacts

    source = tmp_path / "source"
    source_next = tmp_path / "source-next"
    versions = tmp_path / "versions"
    active = tmp_path / "active.json"
    _write_complete_source(source)
    _write_complete_source(source_next)
    (source_next / "model_selection.json").write_text(
        '{"strategy":"lightgbm","weights":{"lstm":0.0,"lightgbm":1.0}}',
        encoding="utf-8",
    )
    first = publish_model_package(source_dir=source, versions_dir=versions, active_file=active)
    second = publish_model_package(
        source_dir=source_next,
        versions_dir=versions,
        active_file=active,
        activate=False,
    )

    env = os.environ.copy()
    backend_dir = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = os.pathsep.join([str(backend_dir), str(backend_dir / "ml")])
    code = (
        "from pathlib import Path\n"
        "from ml.artifacts import get_active_model_dir, get_active_model_id\n"
        f"active = Path({str(active)!r})\n"
        f"versions = Path({str(versions)!r})\n"
        "print(get_active_model_id(active_file=active))\n"
        "print(get_active_model_dir(active_file=active, versions_dir=versions).name)\n"
    )
    restarted = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        check=True,
        env=env,
        text=True,
    )
    assert restarted.stdout.splitlines() == [first["model_id"], first["model_id"]]

    original_replace = artifacts.os.replace

    def fail_pointer_replace(source_path, target_path):
        if Path(target_path) == active:
            raise OSError("simulated activation interruption")
        return original_replace(source_path, target_path)

    monkeypatch.setattr(artifacts.os, "replace", fail_pointer_replace)
    with pytest.raises(OSError, match="activation interruption"):
        artifacts.activate_model(second["model_id"], versions_dir=versions, active_file=active)

    assert get_active_model_id(active_file=active) == first["model_id"]
    assert not list(tmp_path.glob(".active.json.*"))
