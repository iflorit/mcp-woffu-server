"""
Tests for Woffu MCP tools.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Set test environment variables before importing modules
os.environ["WOFFU_TOKEN"] = "test-token"
os.environ["WOFFU_USER_ID"] = "12345"
os.environ["WOFFU_BASE_URL"] = "https://test.woffu.com"

from woffu_mcp.config import WoffuConfig, get_config, reset_config
from woffu_mcp.tools import (
    clock_in,
    clock_out,
    get_today_status,
    get_month_summary,
    complete_day,
)


@pytest.fixture(autouse=True)
def reset_config_before_each():
    """Reset configuration before each test."""
    reset_config()
    yield
    reset_config()


class TestConfig:
    """Tests for configuration module."""

    def test_config_from_env(self):
        """Test loading configuration from environment variables."""
        config = WoffuConfig.from_env()
        assert config.token == "test-token"
        assert config.user_id == "12345"
        assert config.base_url == "https://test.woffu.com"

    def test_config_validation_missing_token(self):
        """Test validation fails when token is missing."""
        config = WoffuConfig(base_url="https://test.woffu.com", token="", user_id="12345")
        error = config.validate()
        assert error is not None
        assert "WOFFU_TOKEN" in error

    def test_config_validation_missing_user_id(self):
        """Test validation fails when user ID is missing."""
        config = WoffuConfig(base_url="https://test.woffu.com", token="test", user_id="")
        error = config.validate()
        assert error is not None
        assert "WOFFU_USER_ID" in error

    def test_config_validation_success(self):
        """Test validation passes with valid config."""
        config = WoffuConfig(
            base_url="https://test.woffu.com",
            token="test-token",
            user_id="12345"
        )
        assert config.validate() is None
        assert config.is_valid


class TestClockIn:
    """Tests for clock_in function."""

    @patch("woffu_mcp.tools.requests.post")
    def test_clock_in_success(self, mock_post):
        """Test successful clock in."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"signEventId": "abc123"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = clock_in()

        assert result["status"] == "success"
        assert result["action"] == "clock_in"
        assert result["signEventId"] == "abc123"
        assert "timestamp" in result

    @patch("woffu_mcp.tools.requests.post")
    def test_clock_in_http_error(self, mock_post):
        """Test clock in with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response
        mock_post.return_value.raise_for_status.side_effect = Exception("401 Unauthorized")

        result = clock_in()

        assert "error" in result


class TestClockOut:
    """Tests for clock_out function."""

    @patch("woffu_mcp.tools.requests.post")
    def test_clock_out_success(self, mock_post):
        """Test successful clock out."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"signEventId": "def456"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = clock_out()

        assert result["status"] == "success"
        assert result["action"] == "clock_out"
        assert result["signEventId"] == "def456"


class TestGetTodayStatus:
    """Tests for get_today_status function."""

    @patch("woffu_mcp.tools.requests.get")
    def test_get_today_status_success(self, mock_get):
        """Test successful status retrieval."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "workedMinutes": 240,
            "expectedMinutes": 480,
            "status": "working"
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_today_status()

        assert result["workedMinutes"] == 240
        assert result["expectedMinutes"] == 480


class TestGetMonthSummary:
    """Tests for get_month_summary function."""

    @patch("woffu_mcp.tools.requests.get")
    def test_get_month_summary_current_month(self, mock_get):
        """Test getting current month summary."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"totalHours": 160}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_month_summary()

        assert result["totalHours"] == 160
        mock_get.assert_called_once()

    @patch("woffu_mcp.tools.requests.get")
    def test_get_month_summary_specific_month(self, mock_get):
        """Test getting specific month summary."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"totalHours": 168}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_month_summary(year=2024, month=6)

        assert result["totalHours"] == 168
        # Verify the URL contains the correct date
        call_url = mock_get.call_args[0][0]
        assert "2024-06-01" in call_url

    def test_get_month_summary_invalid_month(self):
        """Test with invalid month."""
        result = get_month_summary(month=13)
        assert "error" in result


class TestCompleteDay:
    """Tests for complete_day function."""

    @patch("woffu_mcp.tools.requests.put")
    def test_complete_day_success(self, mock_put):
        """Test successful day completion."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_put.return_value = mock_response

        slots = [
            {"in_time": "09:00", "out_time": "14:00"},
            {"in_time": "15:00", "out_time": "18:00"},
        ]
        result = complete_day("2024-01-15", slots)

        assert result["status"] == "success"
        assert result["action"] == "complete_day"
        assert result["date"] == "2024-01-15"
        assert result["slots_count"] == 2

    def test_complete_day_invalid_date_format(self):
        """Test with invalid date format."""
        slots = [{"in_time": "09:00", "out_time": "18:00"}]
        result = complete_day("15-01-2024", slots)
        assert "error" in result
        assert "YYYY-MM-DD" in result["error"]

    def test_complete_day_empty_slots(self):
        """Test with empty slots."""
        result = complete_day("2024-01-15", [])
        assert "error" in result

    def test_complete_day_invalid_time_format(self):
        """Test with invalid time format."""
        slots = [{"in_time": "9am", "out_time": "5pm"}]
        result = complete_day("2024-01-15", slots)
        assert "error" in result

    def test_complete_day_out_before_in(self):
        """Test with out_time before in_time."""
        slots = [{"in_time": "18:00", "out_time": "09:00"}]
        result = complete_day("2024-01-15", slots)
        assert "error" in result
        assert "after" in result["error"].lower()


class TestConfigNotSet:
    """Tests for when configuration is not properly set."""

    def test_clock_in_no_token(self):
        """Test clock in without token."""
        os.environ["WOFFU_TOKEN"] = ""
        reset_config()

        result = clock_in()

        assert "error" in result
        assert "WOFFU_TOKEN" in result["error"]

        # Restore
        os.environ["WOFFU_TOKEN"] = "test-token"

    def test_clock_out_no_user_id(self):
        """Test clock out without user ID."""
        os.environ["WOFFU_USER_ID"] = ""
        reset_config()

        result = clock_out()

        assert "error" in result

        # Restore
        os.environ["WOFFU_USER_ID"] = "12345"
