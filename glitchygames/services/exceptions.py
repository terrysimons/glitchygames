"""Custom exceptions for GlitchyGames services."""


class SpriteServiceError(Exception):
    """Base exception for sprite service errors."""


class AIProviderError(SpriteServiceError):
    """Error communicating with AI provider."""

    def __init__(
        self, message: str, provider: str | None = None, original_error: Exception | None = None,
    ) -> None:
        """Initialize AIProviderError.

        Args:
            message: Error message
            provider: AI provider that caused the error (optional)
            original_error: Original exception that was caught (optional)

        """
        super().__init__(message)
        self.provider = provider
        self.original_error = original_error


class ValidationError(SpriteServiceError):
    """Error validating sprite data or AI response."""

    def __init__(self, message: str, validation_errors: list[str] | None = None) -> None:
        """Initialize ValidationError.

        Args:
            message: Error message
            validation_errors: List of specific validation errors (optional)

        """
        super().__init__(message)
        self.validation_errors = validation_errors or []


class RenderingError(SpriteServiceError):
    """Error rendering sprite to PNG."""

    def __init__(
        self, message: str, sprite_name: str | None = None, original_error: Exception | None = None,
    ) -> None:
        """Initialize RenderingError.

        Args:
            message: Error message
            sprite_name: Name of sprite that failed to render (optional)
            original_error: Original exception that was caught (optional)

        """
        super().__init__(message)
        self.sprite_name = sprite_name
        self.original_error = original_error
