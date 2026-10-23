class AppError(Exception):
    status_code = 400
    error_message = "An error occurred while processing the request"

    def __init__(self, message: str | None = None) -> None:
        # a message passed to the constructor overrides the class default
        if message is not None:
            self.error_message = message
        super().__init__(self.error_message)


class AuthError(AppError):
    status_code = 401
    error_message = "Invalid credentials"


class ForbiddenError(AppError):
    status_code = 403
    error_message = "Insufficient permissions"


class NotFoundError(AppError):
    status_code = 404
    error_message = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    error_message = "Conflict with the current state of the resource"


class UnprocessableError(AppError):
    status_code = 422
    error_message = "The request is well-formed but semantically invalid"


class AuthServiceUnavailableError(AppError):
    status_code = 503
    error_message = "Authentication service is unavailable"
