"""The CI schema generator must expose the standard application's full API."""

import json

from crosfit_training_backend.common.swagger_generator import save_swagger_json
from crosfit_training_backend.main import app


def test_generated_schema_includes_profile_and_statistics(tmp_path):
    output = tmp_path / "swagger.json"
    save_swagger_json(app, str(output))
    paths = json.loads(output.read_text())["paths"]
    expected = {
        "/me": {"get"},
        "/me/profile": {"get", "patch"},
        "/me/body-measurements": {"get"},
        "/me/body-measurements/{measurement_date}": {"get", "put", "delete"},
        "/stats/weekly-tonnage": {"get"},
        "/stats/relative-strength": {"get"},
        "/stats/tonnage": {"get"},
        "/stats/strength-records": {"get"},
        "/stats/distance-bests": {"get"},
    }
    for path, methods in expected.items():
        assert methods <= paths[path].keys()
