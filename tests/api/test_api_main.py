"""Coverage tests for API main module.

Tests cover: create_app factory, run() entry point, and lifespan context manager.
"""

import pytest

# Skip tests if FastAPI is not installed
pytest.importorskip('fastapi')


class TestCreateApp:
    """Test create_app factory function."""

    def test_create_app_returns_fastapi_instance(self):
        """Test that create_app returns a FastAPI app with correct configuration."""
        from glitchygames.api.main import create_app

        application = create_app()

        assert application.title == 'GlitchyGames Sprite Generation API'
        assert application.version == '1.0.0'
        assert application.docs_url == '/docs'
        assert application.redoc_url == '/redoc'

    def test_app_module_level_instance_exists(self):
        """Test that the module-level app instance is created."""
        from glitchygames.api.main import app

        assert app is not None
        assert app.title == 'GlitchyGames Sprite Generation API'

    def test_app_has_routes(self):
        """Test that the app has the expected routes registered."""
        from glitchygames.api.main import app

        route_paths = [route.path for route in app.routes]

        assert '/' in route_paths
        assert '/health' in route_paths


class TestRunEntryPoint:
    """Test run() entry point function."""

    def test_run_uses_default_host_and_port(self, mocker):
        """Test run() uses defaults when env vars are not set."""
        mock_uvicorn_run = mocker.patch('uvicorn.run')
        mocker.patch.dict(
            'os.environ',
            {
                'GLITCHYGAMES_HOST': '127.0.0.1',
                'GLITCHYGAMES_PORT': '8000',
                'GLITCHYGAMES_RELOAD': 'false',
            },
        )

        from glitchygames.api.main import run

        run()

        mock_uvicorn_run.assert_called_once_with(
            'glitchygames.api.main:app',
            host='127.0.0.1',
            port=8000,
            reload=False,
        )

    def test_run_uses_custom_env_vars(self, mocker):
        """Test run() reads custom host, port, reload from environment."""
        all_interfaces_host = '0.0.0.0'  # noqa: S104
        mock_uvicorn_run = mocker.patch('uvicorn.run')
        mocker.patch.dict(
            'os.environ',
            {
                'GLITCHYGAMES_HOST': all_interfaces_host,
                'GLITCHYGAMES_PORT': '9090',
                'GLITCHYGAMES_RELOAD': 'true',
            },
        )

        from glitchygames.api.main import run

        run()

        mock_uvicorn_run.assert_called_once_with(
            'glitchygames.api.main:app',
            host=all_interfaces_host,
            port=9090,
            reload=True,
        )


class TestLifespan:
    """Test application lifespan context manager."""

    def test_lifespan_initializes_renderer(self, mocker):
        """Test that lifespan initializes the RendererService on startup."""
        # Must patch where it's imported in the lifespan function
        mock_renderer_cls = mocker.patch('glitchygames.services.RendererService')

        from fastapi.testclient import TestClient

        from glitchygames.api.main import app

        # TestClient triggers the lifespan context manager
        with TestClient(app):
            pass

        # RendererService should have been called during startup
        mock_renderer_cls.assert_called()
