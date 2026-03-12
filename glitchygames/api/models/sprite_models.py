"""Pydantic models for sprite generation API endpoints."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Valid output format values
OUTPUT_FORMAT_TOML = "toml"
OUTPUT_FORMAT_PNG = "png"
VALID_OUTPUT_FORMATS = [OUTPUT_FORMAT_TOML, OUTPUT_FORMAT_PNG]


class SpriteGenerationRequest(BaseModel):
    """Request model for sprite generation.

    Attributes:
        prompt: Text description of the sprite to generate
        width: Optional sprite width in pixels (1-64)
        height: Optional sprite height in pixels (1-64)
        frame_count: Number of frames per animation (for animated sprites)
        film_strip_count: Number of film strips/animations to create
        animation_duration: Duration of animation in seconds
        output_format: List of output formats to include ('toml', 'png', or both)
        png_scale: Scale factor for PNG output (1-10)

    """

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Text description of the sprite to generate",
        json_schema_extra={"example": "16x16 red heart with a golden outline"},
    )
    width: int | None = Field(
        default=None,
        ge=1,
        le=64,
        description="Sprite width in pixels (1-64). If not specified, AI determines size.",
    )
    height: int | None = Field(
        default=None,
        ge=1,
        le=64,
        description="Sprite height in pixels (1-64). If not specified, AI determines size.",
    )
    frame_count: int = Field(
        default=1,
        ge=1,
        le=32,
        description="Number of frames per animation (1-32). Default: 1 (static sprite).",
    )
    film_strip_count: int | None = Field(
        default=None,
        ge=1,
        le=8,
        description="Number of film strips/animations to create (1-8).",
    )
    animation_duration: float | None = Field(
        default=None,
        gt=0,
        le=60,
        description="Duration of animation in seconds (0-60).",
    )
    output_format: list[Literal["toml", "png"]] = Field(
        default=["toml", "png"],
        description="List of output formats: ['toml'], ['png'], or ['toml', 'png']",
        json_schema_extra={"example": ["toml", "png"]},
    )
    png_scale: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Scale factor for PNG output (1-10)",
    )
    output_path: str | None = Field(
        default=None,
        description="Directory to save output files. Created if it doesn't exist.",
        json_schema_extra={"example": "/path/to/sprites"},
    )
    model: str | None = Field(
        default=None,
        description="AI model override in aisuite format (e.g., 'anthropic:claude-sonnet-4-5')",
        json_schema_extra={"example": "anthropic:claude-sonnet-4-5"},
    )

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, value: list[str]) -> list[str]:
        """Validate that output_format contains valid values and is not empty."""
        if not value:
            raise ValueError("output_format must contain at least one format ('toml' or 'png')")
        for fmt in value:
            if fmt not in VALID_OUTPUT_FORMATS:
                raise ValueError(f"Invalid format '{fmt}'. Must be 'toml' or 'png'")
        return value


class SpriteRefinementRequest(BaseModel):
    """Request model for sprite refinement.

    Attributes:
        prompt: Text description of how to modify the sprite
        current_toml: Current sprite TOML content to refine
        output_format: List of output formats to include ('toml', 'png', or both)
        png_scale: Scale factor for PNG output (1-10)
        output_path: Directory to save output files (optional)

    """

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Text description of how to modify the sprite",
        json_schema_extra={"example": "Make the heart blue instead of red"},
    )
    current_toml: str = Field(
        ...,
        min_length=1,
        description="Current sprite TOML content to refine",
    )
    output_format: list[Literal["toml", "png"]] = Field(
        default=["toml", "png"],
        description="List of output formats: ['toml'], ['png'], or ['toml', 'png']",
        json_schema_extra={"example": ["toml", "png"]},
    )
    png_scale: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Scale factor for PNG output (1-10)",
    )
    output_path: str | None = Field(
        default=None,
        description="Directory to save output files. Created if it doesn't exist.",
        json_schema_extra={"example": "/path/to/sprites"},
    )

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, value: list[str]) -> list[str]:
        """Validate that output_format contains valid values and is not empty."""
        if not value:
            raise ValueError("output_format must contain at least one format ('toml' or 'png')")
        for fmt in value:
            if fmt not in VALID_OUTPUT_FORMATS:
                raise ValueError(f"Invalid format '{fmt}'. Must be 'toml' or 'png'")
        return value


class RenderedFrameInfo(BaseModel):
    """Information about a single rendered frame with animation context.

    Attributes:
        animation_index: Index of the animation (film strip) this frame belongs to
        frame_index: Index of the frame within its animation
        png_base64: Base64-encoded PNG data for this frame

    """

    animation_index: int = Field(
        ...,
        description="Index of the animation (film strip) this frame belongs to",
    )
    frame_index: int = Field(
        ...,
        description="Index of the frame within its animation",
    )
    png_base64: str = Field(
        ...,
        description="Base64-encoded PNG data for this frame",
    )


class SpriteGenerationResponse(BaseModel):
    """Response model for sprite generation.

    Attributes:
        success: Whether the generation was successful
        sprite_name: Name of the generated sprite
        is_animated: Whether the sprite has animation
        frame_count: Number of frames (1 for static sprites)
        width: Sprite width in pixels
        height: Sprite height in pixels
        toml_content: Generated TOML content (if output_format includes TOML)
        png_base64: Base64-encoded PNG of first/current frame (if output_format includes PNG)
        all_frames_png_base64: List of base64 PNGs for all frames (if frame_count > 1)
        rendered_frames: List of frames with animation/frame indices (if frame_count > 1)
        saved_files: List of file paths that were saved (if output_path was specified)
        error: Error message (if success=False)

    """

    success: bool = Field(
        ...,
        description="Whether the generation was successful",
    )
    sprite_name: str | None = Field(
        default=None,
        description="Name of the generated sprite",
    )
    is_animated: bool = Field(
        default=False,
        description="Whether the sprite has animation",
    )
    frame_count: int = Field(
        default=1,
        description="Number of frames (1 for static sprites)",
    )
    width: int | None = Field(
        default=None,
        description="Sprite width in pixels",
    )
    height: int | None = Field(
        default=None,
        description="Sprite height in pixels",
    )
    toml_content: str | None = Field(
        default=None,
        description="Generated TOML sprite definition",
    )
    png_base64: str | None = Field(
        default=None,
        description="Base64-encoded PNG of first/current frame",
    )
    all_frames_png_base64: list[str] | None = Field(
        default=None,
        description="List of base64-encoded PNGs for all animation frames",
    )
    rendered_frames: list[RenderedFrameInfo] | None = Field(
        default=None,
        description="List of frames with animation/frame indices (if frame_count > 1)",
    )
    saved_files: list[str] | None = Field(
        default=None,
        description="List of file paths that were saved (if output_dir was specified)",
    )
    error: str | None = Field(
        default=None,
        description="Error message (if success=False)",
    )


class ApngFrameInfo(BaseModel):
    """Information about a single frame in an APNG.

    Attributes:
        index: Frame index (0-based)
        png_base64: Base64-encoded PNG data for this frame
        delay_ms: Frame delay in milliseconds
        width: Frame width in pixels
        height: Frame height in pixels
        x_offset: X offset of frame within canvas
        y_offset: Y offset of frame within canvas

    """

    index: int = Field(
        ...,
        description="Frame index (0-based)",
    )
    png_base64: str = Field(
        ...,
        description="Base64-encoded PNG data for this frame",
    )
    delay_ms: int = Field(
        ...,
        description="Frame delay in milliseconds",
    )
    width: int = Field(
        ...,
        description="Frame width in pixels",
    )
    height: int = Field(
        ...,
        description="Frame height in pixels",
    )
    x_offset: int = Field(
        default=0,
        description="X offset of frame within canvas",
    )
    y_offset: int = Field(
        default=0,
        description="Y offset of frame within canvas",
    )


class ApngExtractRequest(BaseModel):
    """Request model for APNG frame extraction.

    Attributes:
        apng_base64: Base64-encoded APNG file content

    """

    apng_base64: str = Field(
        ...,
        min_length=1,
        description="Base64-encoded APNG file content",
    )


class ApngExtractResponse(BaseModel):
    """Response model for APNG frame extraction.

    Attributes:
        success: Whether extraction was successful
        frame_count: Total number of frames extracted
        width: Canvas width in pixels
        height: Canvas height in pixels
        loop_count: Number of times animation loops (0 = infinite)
        total_duration_ms: Total animation duration in milliseconds
        frames: List of extracted frame information
        error: Error message (if success=False)

    """

    success: bool = Field(
        ...,
        description="Whether extraction was successful",
    )
    frame_count: int = Field(
        default=0,
        description="Total number of frames extracted",
    )
    width: int | None = Field(
        default=None,
        description="Canvas width in pixels",
    )
    height: int | None = Field(
        default=None,
        description="Canvas height in pixels",
    )
    loop_count: int = Field(
        default=0,
        description="Number of times animation loops (0 = infinite)",
    )
    total_duration_ms: int = Field(
        default=0,
        description="Total animation duration in milliseconds",
    )
    frames: list[ApngFrameInfo] = Field(
        default_factory=list,
        description="List of extracted frame information",
    )
    error: str | None = Field(
        default=None,
        description="Error message (if success=False)",
    )


class HealthResponse(BaseModel):
    """Response model for health check endpoint.

    Attributes:
        status: Service status ("healthy" or "unhealthy")
        version: API version
        ai_provider: Configured AI provider
        ai_model: Configured AI model
        pygame_initialized: Whether pygame is initialized for rendering

    """

    status: str = Field(
        ...,
        description="Service status",
        json_schema_extra={"example": "healthy"},
    )
    version: str = Field(
        ...,
        description="API version",
        json_schema_extra={"example": "1.0.0"},
    )
    ai_provider: str = Field(
        ...,
        description="Configured AI provider",
        json_schema_extra={"example": "anthropic"},
    )
    ai_model: str = Field(
        ...,
        description="Configured AI model",
        json_schema_extra={"example": "claude-sonnet-4-5"},
    )
    pygame_initialized: bool = Field(
        ...,
        description="Whether pygame is initialized for rendering",
    )
