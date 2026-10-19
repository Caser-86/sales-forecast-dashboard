"""JSON scaler serialization tests."""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.preprocessing import StandardScaler


def test_scaler_json_round_trip_preserves_transform(tmp_path):
    from ml.scaler_io import load_scaler, save_scaler

    original = StandardScaler().fit(np.asarray([[1.0, 10.0], [3.0, 14.0], [5.0, 18.0]]))
    path = tmp_path / "scaler.json"
    save_scaler(original, path)
    restored = load_scaler(path)

    np.testing.assert_allclose(restored.transform([[2.0, 12.0]]), original.transform([[2.0, 12.0]]))


def test_scaler_json_rejects_non_finite_parameters(tmp_path):
    from ml.scaler_io import load_scaler

    path = tmp_path / "scaler.json"
    path.write_text(
        '{"mean": [0.0], "scale": [1.0], "var": ["NaN"], "n_features_in": 1, "n_samples_seen": 1}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="有限"):
        load_scaler(path)
