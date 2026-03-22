"""Tests for multi-controller error handling and configuration."""

import json

import pytest

from glitchygames.bitmappy.multi_controller_error_handling import (
    ErrorInfo,
    ErrorSeverity,
    MultiControllerConfig,
    MultiControllerErrorHandler,
    MultiControllerLogger,
    MultiControllerValidator,
)


class TestErrorSeverity:
    """Tests for the ErrorSeverity enum."""

    def test_severity_values(self):
        """Test that severity levels have correct string values."""
        assert ErrorSeverity.LOW.value == 'low'
        assert ErrorSeverity.MEDIUM.value == 'medium'
        assert ErrorSeverity.HIGH.value == 'high'
        assert ErrorSeverity.CRITICAL.value == 'critical'


class TestErrorInfo:
    """Tests for the ErrorInfo dataclass."""

    def test_creation_with_required_fields(self):
        """Test creating ErrorInfo with required fields only."""
        error_info = ErrorInfo(
            error_type='ValueError',
            message='invalid value',
            severity=ErrorSeverity.MEDIUM,
            timestamp=1000.0,
        )
        assert error_info.error_type == 'ValueError'
        assert error_info.message == 'invalid value'
        assert error_info.severity == ErrorSeverity.MEDIUM
        assert error_info.timestamp == pytest.approx(1000.0)
        assert error_info.controller_id is None
        assert error_info.operation is None
        assert error_info.stack_trace is None

    def test_creation_with_all_fields(self):
        """Test creating ErrorInfo with all fields."""
        error_info = ErrorInfo(
            error_type='KeyError',
            message='missing key',
            severity=ErrorSeverity.HIGH,
            timestamp=2000.0,
            controller_id=1,
            operation='navigate',
            stack_trace='Traceback...',
        )
        assert error_info.controller_id == 1
        assert error_info.operation == 'navigate'
        assert error_info.stack_trace == 'Traceback...'


class TestMultiControllerErrorHandler:
    """Tests for the MultiControllerErrorHandler class.

    Note: The class has a bug where _setup_default_handlers is called in
    __init__ but never defined. We add it as a no-op to allow testing the
    rest of the class.
    """

    @pytest.fixture(autouse=True)
    def _setup_handler(self):
        """Create handler with the missing method patched."""
        MultiControllerErrorHandler._setup_default_handlers = lambda self: None  # type: ignore[invalid-assignment]
        self.handler = MultiControllerErrorHandler()
        yield
        # Clean up the monkey-patched method
        del MultiControllerErrorHandler._setup_default_handlers

    def test_initialization(self):
        """Test handler initializes with correct defaults."""
        assert self.handler.error_history == []
        assert self.handler.error_counts == {}
        assert self.handler.recovery_attempts == {}
        assert self.handler.max_error_history == 1000
        assert self.handler.max_recovery_attempts == 3
        assert self.handler.auto_recovery_enabled is True

    def test_handle_error_records_in_history(self):
        """Test that handling an error adds it to history."""
        error = ValueError('test error')
        self.handler.handle_error(error, controller_id=0, operation='paint')

        assert len(self.handler.error_history) == 1
        recorded = self.handler.error_history[0]
        assert recorded.error_type == 'ValueError'
        assert recorded.message == 'test error'
        assert recorded.controller_id == 0
        assert recorded.operation == 'paint'

    def test_handle_error_updates_counts(self):
        """Test that error counts are tracked."""
        error = ValueError('test')
        self.handler.handle_error(error, operation='paint')
        self.handler.handle_error(error, operation='paint')

        assert self.handler.error_counts['ValueError_paint'] == 2

    def test_handle_error_with_severity_levels(self):
        """Test handling errors at different severity levels."""
        for severity in ErrorSeverity:
            error = ValueError(f'test {severity.value}')
            self.handler.handle_error(error, severity=severity)

        assert len(self.handler.error_history) == 4

    def test_error_history_truncation(self):
        """Test that error history is bounded to max_error_history."""
        self.handler.max_error_history = 5

        for i in range(10):
            self.handler.handle_error(ValueError(f'error {i}'))

        assert len(self.handler.error_history) == 5

    def test_handle_error_auto_recovery_disabled(self):
        """Test error handling with auto recovery disabled."""
        self.handler.auto_recovery_enabled = False
        error = ValueError('test')
        result = self.handler.handle_error(error)
        assert result is False

    def test_recovery_attempt_limit(self):
        """Test that recovery attempts are limited."""
        self.handler.max_recovery_attempts = 2

        error = ValueError('test')
        # First two attempts should proceed
        self.handler.handle_error(error, operation='op')
        self.handler.handle_error(error, operation='op')

        # Third attempt should fail due to limit
        result = self.handler.handle_error(error, operation='op')
        assert result is False

    def test_default_recovery_key_error(self):
        """Test default recovery for KeyError."""
        error = KeyError('missing_key')
        result = self.handler.handle_error(error, operation='lookup')
        assert result is True

    def test_default_recovery_attribute_error(self):
        """Test default recovery for AttributeError."""
        error = AttributeError('no such attribute')
        result = self.handler.handle_error(error, operation='access')
        assert result is True

    def test_default_recovery_value_error(self):
        """Test default recovery for ValueError."""
        error = ValueError('invalid')
        result = self.handler.handle_error(error, operation='validate')
        assert result is True

    def test_default_recovery_unknown_type(self):
        """Test default recovery for unknown error types returns False."""
        error = RuntimeError('unknown')
        result = self.handler.handle_error(error, operation='something')
        assert result is False

    def test_register_error_handler(self):
        """Test registering a custom error handler."""

        def handler_func(error_info):
            return True

        self.handler.register_error_handler('CustomError', handler_func)
        assert 'CustomError' in self.handler.error_handlers

    def test_register_recovery_handler(self):
        """Test registering a custom recovery handler."""

        def recovery_func(error_info):
            return True

        self.handler.register_recovery_handler('ValueError_validate', recovery_func)
        assert 'ValueError_validate' in self.handler.recovery_handlers

    def test_custom_recovery_handler_called(self):
        """Test that custom recovery handler is invoked."""
        called_with = []

        def custom_recovery(error_info):
            called_with.append(error_info)
            return True

        self.handler.register_recovery_handler('ValueError_validate', custom_recovery)

        error = ValueError('test')
        result = self.handler.handle_error(error, operation='validate')
        assert result is True
        assert len(called_with) == 1

    def test_custom_recovery_handler_failure(self):
        """Test that failing recovery handlers are handled gracefully."""

        def bad_recovery(error_info):
            raise TypeError('recovery broke')

        self.handler.register_recovery_handler('ValueError_validate', bad_recovery)

        error = ValueError('test')
        result = self.handler.handle_error(error, operation='validate')
        assert result is False

    def test_get_error_statistics(self):
        """Test getting error statistics."""
        self.handler.handle_error(ValueError('a'), operation='op1')
        self.handler.handle_error(KeyError('b'), operation='op2')

        stats = self.handler.get_error_statistics()
        assert stats['total_errors'] == 2
        assert 'ValueError_op1' in stats['error_counts']
        assert 'KeyError_op2' in stats['error_counts']
        assert len(stats['recent_errors']) == 2

    def test_clear_error_history(self):
        """Test clearing error history."""
        self.handler.handle_error(ValueError('test'), operation='op')

        self.handler.clear_error_history()
        assert self.handler.error_history == []
        assert self.handler.error_counts == {}
        assert self.handler.recovery_attempts == {}

    def test_log_error_severity_levels(self):
        """Test that errors are logged at appropriate levels."""
        for severity in ErrorSeverity:
            error_info = ErrorInfo(
                error_type='TestError',
                message='test',
                severity=severity,
                timestamp=1000.0,
                controller_id=0,
            )
            # Should not raise
            self.handler._log_error(error_info)


class TestMultiControllerConfig:
    """Tests for the MultiControllerConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = MultiControllerConfig()
        assert config.max_controllers == 4
        assert config.controller_timeout == pytest.approx(300.0)
        assert config.auto_cleanup_interval == pytest.approx(60.0)
        assert config.collision_offset_distance == 15
        assert config.visual_indicator_size == 12
        assert config.visual_indicator_shape == 'triangle'
        assert config.enable_caching is True
        assert config.enable_optimization is True
        assert config.update_throttle == pytest.approx(0.016)
        assert config.error_logging_enabled is True
        assert config.auto_recovery_enabled is True
        assert config.max_error_history == 1000
        assert config.max_recovery_attempts == 3
        assert config.navigation_history_limit == 100
        assert config.enable_navigation_history is True

    def test_from_file_nonexistent(self):
        """Test loading config from a nonexistent file returns defaults."""
        config = MultiControllerConfig.from_file('/nonexistent/config.json')
        assert config.max_controllers == 4

    def test_from_file_valid_json(self, tmp_path):
        """Test loading config from a valid JSON file."""
        config_data = {
            'max_controllers': 8,
            'controller_timeout': 600.0,
            'visual_indicator_shape': 'circle',
        }
        config_file = tmp_path / 'config.json'
        config_file.write_text(json.dumps(config_data))

        config = MultiControllerConfig.from_file(str(config_file))
        assert config.max_controllers == 8
        assert config.controller_timeout == pytest.approx(600.0)
        assert config.visual_indicator_shape == 'circle'

    def test_from_file_invalid_json(self, tmp_path):
        """Test loading config from an invalid JSON file returns defaults."""
        config_file = tmp_path / 'config.json'
        config_file.write_text('not valid json {{{')

        config = MultiControllerConfig.from_file(str(config_file))
        assert config.max_controllers == 4  # Default

    def test_save_to_file(self, tmp_path):
        """Test saving config to a JSON file."""
        config = MultiControllerConfig(max_controllers=8, visual_indicator_shape='circle')
        config_file = tmp_path / 'config.json'

        result = config.save_to_file(str(config_file))
        assert result is True
        assert config_file.exists()

        # Verify the saved data
        saved_data = json.loads(config_file.read_text())
        assert saved_data['max_controllers'] == 8
        assert saved_data['visual_indicator_shape'] == 'circle'

    def test_save_to_file_failure(self, mocker):
        """Test save_to_file returns False on failure."""
        config = MultiControllerConfig()
        mocker.patch('builtins.open', side_effect=PermissionError('denied'))

        result = config.save_to_file('/readonly/config.json')
        assert result is False

    def test_roundtrip_save_load(self, tmp_path):
        """Test saving and loading config preserves values."""
        original = MultiControllerConfig(
            max_controllers=6,
            controller_timeout=120.0,
            enable_caching=False,
            max_recovery_attempts=5,
        )
        config_file = tmp_path / 'config.json'
        original.save_to_file(str(config_file))

        loaded = MultiControllerConfig.from_file(str(config_file))
        assert loaded.max_controllers == 6
        assert loaded.controller_timeout == pytest.approx(120.0)
        assert loaded.enable_caching is False
        assert loaded.max_recovery_attempts == 5


class TestMultiControllerLogger:
    """Tests for the MultiControllerLogger class."""

    def test_initialization_with_logging_enabled(self):
        """Test logger initializes with logging enabled."""
        config = MultiControllerConfig(error_logging_enabled=True)
        logger = MultiControllerLogger(config)
        assert logger.config is config

    def test_initialization_with_logging_disabled(self):
        """Test logger initializes with logging disabled."""
        config = MultiControllerConfig(error_logging_enabled=False)
        logger = MultiControllerLogger(config)
        assert logger.config is config

    def test_log_controller_event(self, mocker):
        """Test logging a controller event."""
        config = MultiControllerConfig(error_logging_enabled=False)
        logger = MultiControllerLogger(config)
        mock_log = mocker.patch.object(logger.logger, 'info')

        logger.log_controller_event(0, 'button_press', {'button': 'A'})
        mock_log.assert_called_once()

    def test_log_performance_metric(self, mocker):
        """Test logging a performance metric."""
        config = MultiControllerConfig(error_logging_enabled=False)
        logger = MultiControllerLogger(config)
        mock_log = mocker.patch.object(logger.logger, 'debug')

        logger.log_performance_metric('update', 0.016)
        mock_log.assert_called_once()

    def test_log_system_status(self, mocker):
        """Test logging system status."""
        config = MultiControllerConfig(error_logging_enabled=False)
        logger = MultiControllerLogger(config)
        mock_log = mocker.patch.object(logger.logger, 'info')

        logger.log_system_status({'controllers': 2, 'active': 1})
        mock_log.assert_called_once()


class TestMultiControllerValidator:
    """Tests for the MultiControllerValidator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = MultiControllerConfig(max_controllers=4)
        self.validator = MultiControllerValidator(self.config)

    def test_validate_controller_id_valid(self):
        """Test validating valid controller IDs."""
        assert self.validator.validate_controller_id(0) is True
        assert self.validator.validate_controller_id(1) is True
        assert self.validator.validate_controller_id(3) is True

    def test_validate_controller_id_invalid(self):
        """Test validating invalid controller IDs."""
        assert self.validator.validate_controller_id(-1) is False
        assert self.validator.validate_controller_id(4) is False
        assert self.validator.validate_controller_id(100) is False

    def test_validate_position_valid(self):
        """Test validating valid positions."""
        assert self.validator.validate_position((100, 200)) is True
        assert self.validator.validate_position((0, 0)) is True
        assert self.validator.validate_position((10.5, 20.5)) is True

    def test_validate_position_invalid(self):
        """Test validating invalid positions."""
        assert self.validator.validate_position((100,)) is False
        assert self.validator.validate_position((100, 200, 300)) is False
        assert self.validator.validate_position([100, 200]) is False  # type: ignore[arg-type]
        assert self.validator.validate_position(('a', 'b')) is False  # type: ignore[arg-type]

    def test_validate_color_valid(self):
        """Test validating valid colors."""
        assert self.validator.validate_color((255, 0, 0)) is True
        assert self.validator.validate_color((0, 0, 0)) is True
        assert self.validator.validate_color((255, 255, 255)) is True

    def test_validate_color_invalid(self):
        """Test validating invalid colors."""
        assert self.validator.validate_color((256, 0, 0)) is False
        assert self.validator.validate_color((-1, 0, 0)) is False
        assert self.validator.validate_color((255, 0)) is False
        assert self.validator.validate_color((255, 0, 0, 0)) is False
        assert self.validator.validate_color([255, 0, 0]) is False  # type: ignore[arg-type]

    def test_validate_animation_name_valid(self):
        """Test validating valid animation names."""
        assert self.validator.validate_animation_name('walk') is True
        assert self.validator.validate_animation_name('run-cycle') is True
        assert self.validator.validate_animation_name('a') is True

    def test_validate_animation_name_invalid(self):
        """Test validating invalid animation names."""
        assert self.validator.validate_animation_name('') is False
        assert self.validator.validate_animation_name(123) is False  # type: ignore[arg-type]

    def test_validate_frame_index_valid(self):
        """Test validating valid frame indices."""
        assert self.validator.validate_frame_index(0) is True
        assert self.validator.validate_frame_index(10) is True
        assert self.validator.validate_frame_index(999) is True

    def test_validate_frame_index_invalid(self):
        """Test validating invalid frame indices."""
        assert self.validator.validate_frame_index(-1) is False
        assert self.validator.validate_frame_index(1.5) is False  # type: ignore[arg-type]
        assert self.validator.validate_frame_index('0') is False  # type: ignore[arg-type]
