"""
Configuration management for Woffu MCP Server.
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


@dataclass
class WoffuConfig:
    """Configuration for Woffu API."""

    base_url: str
    token: str
    user_id: str

    @classmethod
    def from_env(cls) -> "WoffuConfig":
        """Create configuration from environment variables."""
        token = os.getenv("WOFFU_TOKEN", "")
        user_id = os.getenv("WOFFU_USER_ID", "")
        base_url = os.getenv("WOFFU_BASE_URL", "https://app.woffu.com")

        return cls(
            base_url=base_url,
            token=token,
            user_id=user_id,
        )

    def validate(self) -> Optional[str]:
        """
        Validate the configuration.

        Returns:
            Error message if invalid, None if valid.
        """
        if not self.token:
            return "WOFFU_TOKEN environment variable is not set"
        if not self.user_id:
            return "WOFFU_USER_ID environment variable is not set"
        return None

    @property
    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return self.validate() is None


# Global configuration instance
_config: Optional[WoffuConfig] = None


def get_config() -> WoffuConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = WoffuConfig.from_env()
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
