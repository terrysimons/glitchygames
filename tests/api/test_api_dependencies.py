"""Coverage tests for API dependencies module.

Tests cover: get_config, get_sprite_generation_service, get_renderer_service
cached dependency injection functions.
"""

import pytest

# Skip tests if FastAPI is not installed
pytest.importorskip('fastapi')

from glitchygames.api.dependencies import (
    get_config,
    get_renderer_service,
    get_sprite_generation_service,
)


class TestGetConfig:
    """Test get_config dependency."""

    def test_get_config_returns_service_config(self, mocker):
        """Test that get_config returns a ServiceConfig instance."""
        # Clear the lru_cache to ensure fresh call
        get_config.cache_clear()

        config = get_config()

        from glitchygames.services.config import ServiceConfig

        assert isinstance(config, ServiceConfig)

        # Clean up cache after test
        get_config.cache_clear()

    def test_get_config_is_cached(self, mocker):
        """Test that get_config returns the same instance on multiple calls."""
        get_config.cache_clear()

        config_first = get_config()
        config_second = get_config()

        assert config_first is config_second

        get_config.cache_clear()


class TestGetSpriteGenerationService:
    """Test get_sprite_generation_service dependency."""

    def test_returns_sprite_generation_service(self, mocker):
        """Test that get_sprite_generation_service returns the correct type."""
        get_sprite_generation_service.cache_clear()
        get_config.cache_clear()

        service = get_sprite_generation_service()

        from glitchygames.services.sprite_generation_service import SpriteGenerationService

        assert isinstance(service, SpriteGenerationService)

        get_sprite_generation_service.cache_clear()
        get_config.cache_clear()

    def test_is_cached(self, mocker):
        """Test that get_sprite_generation_service returns the same instance."""
        get_sprite_generation_service.cache_clear()
        get_config.cache_clear()

        service_first = get_sprite_generation_service()
        service_second = get_sprite_generation_service()

        assert service_first is service_second

        get_sprite_generation_service.cache_clear()
        get_config.cache_clear()


class TestGetRendererService:
    """Test get_renderer_service dependency."""

    def test_returns_renderer_service(self, mocker):
        """Test that get_renderer_service returns a RendererService instance."""
        get_renderer_service.cache_clear()
        get_config.cache_clear()

        # Mock RendererService to avoid needing pygame display
        mock_renderer_cls = mocker.patch(
            'glitchygames.api.dependencies.RendererService',
        )
        mock_instance = mocker.MagicMock()
        mock_renderer_cls.return_value = mock_instance

        service = get_renderer_service()

        assert service is mock_instance

        get_renderer_service.cache_clear()
        get_config.cache_clear()

    def test_is_cached(self, mocker):
        """Test that get_renderer_service returns the same instance."""
        get_renderer_service.cache_clear()
        get_config.cache_clear()

        mock_renderer_cls = mocker.patch(
            'glitchygames.api.dependencies.RendererService',
        )
        mock_instance = mocker.MagicMock()
        mock_renderer_cls.return_value = mock_instance

        service_first = get_renderer_service()
        service_second = get_renderer_service()

        assert service_first is service_second

        get_renderer_service.cache_clear()
        get_config.cache_clear()
