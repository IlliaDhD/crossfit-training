"""Layering guard: controllers (routes) stay thin, services know nothing about HTTP.

Routes only parse the request, call a service and build the response. Database
access, query building and business rules belong to `services/`.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).parent.parent / "src" / "crosfit_training_backend"
ROUTES = sorted((PACKAGE / "api" / "routes").glob("*.py"))
SERVICES = sorted((PACKAGE / "services").glob("*.py"))

# what a route must not do itself
FORBIDDEN_ROUTE_IMPORTS = {"pymongo", "re", "crosfit_training_backend.exceptions"}
FORBIDDEN_ROUTE_NAMES = {"HTTPException"}
FORBIDDEN_ROUTE_CALLS = {
    "find",
    "find_one",
    "find_all",
    "aggregate",
    "count",
    "insert",
    "save",
    "delete",
    "get_pymongo_collection",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imported_modules(tree: ast.Module) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _ids(paths: list[Path]) -> list[str]:
    return [p.name for p in paths]


def test_routes_and_services_are_found():
    assert {"trainings.py", "complexes.py", "exercises.py"} <= {p.name for p in ROUTES}
    assert {"trainings.py", "complexes.py", "exercises.py"} <= {
        p.name for p in SERVICES
    }


@pytest.mark.parametrize("path", ROUTES, ids=_ids(ROUTES))
def test_route_has_no_database_access_or_http_errors(path):
    tree = _tree(path)

    imported = _imported_modules(tree)
    assert not (imported & FORBIDDEN_ROUTE_IMPORTS), (
        f"{path.name} imports {imported & FORBIDDEN_ROUTE_IMPORTS}: move that logic "
        "to a service (domain errors are raised there)"
    )

    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {
        a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names
    }
    assert not (names & FORBIDDEN_ROUTE_NAMES), (
        f"{path.name} uses {names & FORBIDDEN_ROUTE_NAMES}: raise a domain error "
        "from the service instead"
    )

    # `@router.delete(...)` declares a route, it is not a database call
    calls = {
        n.func.attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and not (isinstance(n.func.value, ast.Name) and n.func.value.id == "router")
    }
    assert not (calls & FORBIDDEN_ROUTE_CALLS), (
        f"{path.name} calls {calls & FORBIDDEN_ROUTE_CALLS} directly: "
        "database access belongs to a service"
    )


@pytest.mark.parametrize("path", SERVICES, ids=_ids(SERVICES))
def test_service_does_not_depend_on_http_layer(path):
    imported = _imported_modules(_tree(path))
    http_prefixes = ("fastapi.", "crosfit_training_backend.api.routes")
    http_layer = {
        m
        for m in imported
        if m in ("fastapi", "crosfit_training_backend.api.dependencies")
        or m.startswith(http_prefixes)
    }
    assert not http_layer, f"{path.name} imports the HTTP layer: {http_layer}"
