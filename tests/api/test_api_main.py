"""Coverage tests for API main module.

Tests cover: create_app factory, run() entry point, and lifespan context manager.
"""
# pyright: reportMissingImports=false

import os
import sys
from http import HTTPStatus

import pytest

from glitchygames.process import OutputCapture, run_command

# Skip tests if FastAPI is not installed
pytest.importorskip('fastapi')

# A fresh interpreter importing the API starts in a few seconds (FastAPI, pygame)
CHILD_TIMEOUT_SECONDS = 120.0
EXPECTED_API_PATHS = {
    '/',
    '/health',
    '/sprites/extract-frames',
    '/sprites/generate',
    '/sprites/refine',
}


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

    def test_app_documents_exactly_the_expected_paths(self):
        """Test the public OpenAPI schema lists exactly the expected endpoints.

        Uses the schema rather than app.routes: FastAPI>=0.143 stores included routers
        as _IncludedRouter entries without a .path, and the schema is the contract
        clients actually depend on.
        """
        from glitchygames.api.main import app

        assert set(app.openapi()['paths']) == EXPECTED_API_PATHS

    def test_every_documented_endpoint_is_routable(self):
        """Test every documented path/method pair reaches a handler (no 404/405).

        Requests carry no body, so endpoints that need one fail validation (422)
        before their handler runs; nothing is generated or extracted.
        """
        from fastapi.testclient import TestClient

        from glitchygames.api.main import app

        client = TestClient(app)
        unroutable = []
        for path, operations in app.openapi()['paths'].items():
            for method in operations:
                status_code = client.request(method.upper(), path).status_code
                if status_code in {HTTPStatus.NOT_FOUND, HTTPStatus.METHOD_NOT_ALLOWED}:
                    unroutable.append(f'{method.upper()} {path} -> {status_code}')
        assert not unroutable, f'Documented endpoints not routable: {unroutable}'


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
        all_interfaces_host = '0.0.0.0'  # ruff: ignore[hardcoded-bind-all-interfaces]
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


class TestServerLogging:
    """The server configures its logging as it starts, never at import (BUGS.md #236)."""

    def test_the_server_logs_info_once_it_starts_and_importing_configures_nothing(self):
        """In a fresh interpreter: the import leaves the root alone; starting configures it."""
        probe = (
            'import logging; import glitchygames.api.main as main; root = logging.getLogger(); '
            'print(logging.getLevelName(root.level), len(root.handlers)); '
            'main.configure_server_logging(); '
            'print(logging.getLevelName(root.level), len(root.handlers))'
        )

        completed = run_command(
            command=[sys.executable, '-c', probe],
            environment=os.environ,
            timeout_seconds=CHILD_TIMEOUT_SECONDS,
            capture_output=OutputCapture.APART,
        )

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines()[-2:] == ['WARNING 0', 'INFO 1']
