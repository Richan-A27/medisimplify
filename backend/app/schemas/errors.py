from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Uniform error body. `code` is machine-readable; `message` is safe to show users."""

    code: str
    message: str
