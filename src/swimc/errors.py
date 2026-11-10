"""Error types shared by the Swim compiler."""

from __future__ import annotations


class SwimError(Exception):
    """A user facing diagnostic with source location information."""

    def __init__(
        self,
        message: str,
        filename: str | None = None,
        line: int | None = None,
        col: int | None = None,
        source: str | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.filename = filename
        self.line = line
        self.col = col
        self.source = source
        self.hint = hint

    def render(self) -> str:
        head = "error: " + self.message
        if self.hint:
            head += f"\n  hint: {self.hint}"
        if self.filename:
            loc = self.filename
            if self.line is not None:
                loc += f":{self.line}"
                if self.col is not None:
                    loc += f":{self.col}"
            return f"{loc}: {head}"
        return head


class CompileError(SwimError):
    """Raised when Nim rejects the generated program."""
