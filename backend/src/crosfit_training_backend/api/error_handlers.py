from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from crosfit_training_backend.exceptions import AppError


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        headers = None
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            headers = {"WWW-Authenticate": "Bearer"}
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.error_message},
            headers=headers,
        )
