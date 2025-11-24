"""
MCP Server for Woffu time tracking.

This module implements the Model Context Protocol server that exposes
Woffu time tracking tools to AI assistants like Claude.
"""

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
)

from .tools import (
    clock_in,
    clock_out,
    get_today_status,
    get_month_summary,
    complete_day,
    get_week_summary,
    get_day_detail,
    get_pending_days,
    get_schedule,
)
from .config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("woffu-mcp")

# Create the MCP server instance
server = Server("woffu-mcp-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Woffu tools."""
    return [
        Tool(
            name="woffu_clock_in",
            description="Clock in (fichar entrada) to Woffu time tracking system. "
            "Use this when the user wants to start their workday or register their arrival.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="woffu_clock_out",
            description="Clock out (fichar salida) from Woffu time tracking system. "
            "Use this when the user wants to end their workday or register their departure.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="woffu_status",
            description="Get today's work status from Woffu including current clock state, "
            "hours worked, expected hours, and schedule information.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="woffu_month_summary",
            description="Get a monthly summary of worked hours from Woffu. "
            "Shows daily breakdowns, total hours, and any discrepancies.",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "Year for the summary (defaults to current year)",
                    },
                    "month": {
                        "type": "integer",
                        "description": "Month for the summary, 1-12 (defaults to current month)",
                        "minimum": 1,
                        "maximum": 12,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="woffu_complete_day",
            description="Complete or edit time entries for a past day in Woffu. "
            "Use this to fill in missing clock entries or correct past records. "
            "Requires the date and one or more time slots with in/out times.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date to complete in YYYY-MM-DD format (e.g., 2024-01-15)",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                    },
                    "slots": {
                        "type": "array",
                        "description": "List of time slots for the day",
                        "items": {
                            "type": "object",
                            "properties": {
                                "in_time": {
                                    "type": "string",
                                    "description": "Clock in time in HH:MM format (e.g., 09:00)",
                                    "pattern": "^\\d{2}:\\d{2}$",
                                },
                                "out_time": {
                                    "type": "string",
                                    "description": "Clock out time in HH:MM format (e.g., 18:00)",
                                    "pattern": "^\\d{2}:\\d{2}$",
                                },
                            },
                            "required": ["in_time", "out_time"],
                        },
                        "minItems": 1,
                    },
                },
                "required": ["date", "slots"],
            },
        ),
        Tool(
            name="woffu_week_summary",
            description="Get a weekly summary of worked hours from Woffu. "
            "Shows daily breakdowns for the week containing the specified date.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Any date within the desired week in YYYY-MM-DD format. "
                        "Defaults to current week if not provided.",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="woffu_day_detail",
            description="Get detailed information for a specific day including "
            "all clock events, breaks, and time calculations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format. Defaults to today if not provided.",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="woffu_pending_days",
            description="Get a list of days without completed hours (pending days). "
            "These are workdays where no hours have been logged yet.",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "Year (defaults to current year)",
                    },
                    "month": {
                        "type": "integer",
                        "description": "Month 1-12 (defaults to current month)",
                        "minimum": 1,
                        "maximum": 12,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="woffu_schedule",
            description="Get the user's assigned work schedule including work hours, "
            "office location, and schedule details.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls from the MCP client."""
    logger.info(f"Tool called: {name} with arguments: {arguments}")

    try:
        if name == "woffu_clock_in":
            result = clock_in()
        elif name == "woffu_clock_out":
            result = clock_out()
        elif name == "woffu_status":
            result = get_today_status()
        elif name == "woffu_month_summary":
            year = arguments.get("year")
            month = arguments.get("month")
            result = get_month_summary(year=year, month=month)
        elif name == "woffu_complete_day":
            date = arguments.get("date")
            slots = arguments.get("slots", [])
            if not date:
                result = {"error": "date parameter is required"}
            elif not slots:
                result = {"error": "slots parameter is required and must not be empty"}
            else:
                result = complete_day(date=date, slots=slots)
        elif name == "woffu_week_summary":
            date = arguments.get("date")
            result = get_week_summary(date=date)
        elif name == "woffu_day_detail":
            date = arguments.get("date")
            result = get_day_detail(date=date)
        elif name == "woffu_pending_days":
            year = arguments.get("year")
            month = arguments.get("month")
            result = get_pending_days(year=year, month=month)
        elif name == "woffu_schedule":
            result = get_schedule()
        else:
            result = {"error": f"Unknown tool: {name}"}

        # Format the result as JSON for readability
        result_text = json.dumps(result, indent=2, ensure_ascii=False)

        return [TextContent(type="text", text=result_text)]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        error_result = {"error": str(e)}
        return [TextContent(type="text", text=json.dumps(error_result))]


async def run_server():
    """Run the MCP server using stdio transport."""
    config = get_config()
    validation_error = config.validate()

    if validation_error:
        logger.warning(f"Configuration warning: {validation_error}")
        logger.warning("Some tools may not work until configuration is provided.")
    else:
        logger.info(f"Woffu MCP Server configured for: {config.base_url}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    """Main entry point for the Woffu MCP server."""
    logger.info("Starting Woffu MCP Server...")
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
