"""
MCP Woffu Server - Model Context Protocol server for Woffu time tracking.
"""

__version__ = "0.1.0"
__author__ = "Ismael Florit"

from .server import main
from .tools import (
    clock_in,
    clock_out,
    get_today_status,
    get_month_summary,
    complete_day,
)

__all__ = [
    "main",
    "clock_in",
    "clock_out",
    "get_today_status",
    "get_month_summary",
    "complete_day",
]
