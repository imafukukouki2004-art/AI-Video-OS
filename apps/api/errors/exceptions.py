"""Application-defined exceptions."""


class ApplicationError(Exception):
    """A safe, client-visible application error."""

    def __init__(
        self,
        *,
        code: str = "APPLICATION_ERROR",
        message: str = "The application could not process the request.",
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
