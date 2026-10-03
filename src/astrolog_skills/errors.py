"""User-facing errors: every failure says what went wrong and what to do next."""


class AstroError(Exception):
    """An expected failure with a human message and an optional concrete fix."""

    def __init__(self, message: str, fix: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.fix = fix

    def to_dict(self) -> dict[str, object]:
        return {"ok": False, "error": self.message, "fix": self.fix}
