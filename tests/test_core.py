"""Unit tests for the CLI in filegetter.core."""

from unittest.mock import Mock, patch

from click.testing import CliRunner

from filegetter import __version__
from filegetter.core import cli


class TestCLI:
    def test_help(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "run" in result.output

    def test_version(self):
        result = CliRunner().invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_run_help(self):
        result = CliRunner().invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "--projectpath" in result.output
        assert "--verbose" in result.output
        assert "--dry-run" in result.output
        assert "--limit" in result.output
        assert "--refresh" in result.output

    @patch("filegetter.core.FilegetterBuilder")
    def test_run_default(self, mock_builder_class):
        mock_builder = Mock()
        mock_builder_class.return_value = mock_builder
        mock_builder.run.return_value = {"failed": 0}

        result = CliRunner().invoke(cli, ["run"])

        assert result.exit_code == 0
        mock_builder_class.assert_called_once_with(None)
        mock_builder.run.assert_called_once_with(dry_run=False, limit=None, refresh=False)

    @patch("filegetter.core.FilegetterBuilder")
    def test_run_with_projectpath(self, mock_builder_class):
        mock_builder = Mock()
        mock_builder_class.return_value = mock_builder
        mock_builder.run.return_value = {"failed": 0}

        result = CliRunner().invoke(cli, ["run", "--projectpath", "/custom/path"])

        assert result.exit_code == 0
        mock_builder_class.assert_called_with("/custom/path")

    @patch("filegetter.core.FilegetterBuilder")
    def test_run_verbose_flag_needs_no_value(self, mock_builder_class):
        """--verbose must be a flag, not an option requiring a value."""
        mock_builder = Mock()
        mock_builder_class.return_value = mock_builder
        mock_builder.run.return_value = {"failed": 0}

        result = CliRunner().invoke(cli, ["run", "--verbose"])

        assert result.exit_code == 0
        mock_builder.run.assert_called_once()

    @patch("filegetter.core.FilegetterBuilder")
    def test_run_all_options(self, mock_builder_class):
        mock_builder = Mock()
        mock_builder_class.return_value = mock_builder
        mock_builder.run.return_value = {"failed": 0}

        result = CliRunner().invoke(
            cli, ["run", "-p", "/test/path", "-v", "--dry-run", "--limit", "5", "--refresh"]
        )

        assert result.exit_code == 0
        mock_builder.run.assert_called_once_with(dry_run=True, limit=5, refresh=True)

    @patch("filegetter.core.FilegetterBuilder")
    def test_run_exit_code_on_failures(self, mock_builder_class):
        mock_builder = Mock()
        mock_builder_class.return_value = mock_builder
        mock_builder.run.return_value = {"failed": 3}

        result = CliRunner().invoke(cli, ["run"])

        assert result.exit_code == 1

    @patch("filegetter.core.FilegetterBuilder")
    def test_run_exit_zero_without_failures(self, mock_builder_class):
        mock_builder = Mock()
        mock_builder_class.return_value = mock_builder
        mock_builder.run.return_value = {"failed": 0, "downloaded": 2}

        result = CliRunner().invoke(cli, ["run"])

        assert result.exit_code == 0

    @patch("filegetter.core.FilegetterBuilder", side_effect=Exception("boom"))
    def test_run_unexpected_error(self, mock_builder_class):
        result = CliRunner().invoke(cli, ["run"])
        assert result.exit_code != 0


class TestConfigErrorHandling:
    @patch("filegetter.core.FilegetterBuilder")
    def test_config_error_becomes_clean_message(self, mock_builder_class):
        from filegetter.core import ConfigError

        mock_builder_class.side_effect = ConfigError("Config file not found: x")
        result = CliRunner().invoke(cli, ["run"])

        assert result.exit_code == 1
        assert "Config file not found" in result.output


class TestLogging:
    def test_configure_logging_levels(self):
        import logging

        from filegetter.core import configure_logging

        configure_logging(False)
        assert logging.getLogger().level == logging.INFO

        configure_logging(True)
        assert logging.getLogger().level == logging.DEBUG
