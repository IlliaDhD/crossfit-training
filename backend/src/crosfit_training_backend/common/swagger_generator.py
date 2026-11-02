import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI  # noqa: E402

from crosfit_training_backend.main import app  # noqa: E402


def save_swagger_json(app: FastAPI, path: str) -> None:
    """
    Save the Swagger JSON documentation to a file.
    :param app:
    :param path:
    :return:
    """

    openapi_schema = app.openapi()

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(openapi_schema, f, indent=4)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the Swagger/OpenAPI JSON documentation."
    )
    parser.add_argument(
        "--path",
        type=str,
        help="Path to the output swagger.json file "
        "(default: docs/api-docs/swagger.json).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    save_swagger_json(app, args.path)

