# MCP Woffu Server

A Model Context Protocol (MCP) server for Woffu time tracking integration. This server allows AI assistants like Claude to interact with your Woffu account for clock-in/out operations and time tracking management.

## Features

- **Clock In/Out**: Start and end your workday with simple commands
- **Today's Status**: Check your current work status, hours worked, and schedule
- **Week/Month Summary**: Get a comprehensive overview of your worked hours
- **Complete Past Days**: Fill in missing time entries for past dates
- **Pending Days**: View days without logged hours
- **Confirm Days**: Confirm (accept) workday diaries

## Installation

### Using npx from GitHub (recommended)

```bash
npx github:iflorit/mcp-woffu-server
```

### Installing globally from GitHub

```bash
npm install -g github:iflorit/mcp-woffu-server
mcp-woffu-server
```

### From source

```bash
git clone https://github.com/iflorit/mcp-woffu-server.git
cd mcp-woffu-server
npm install
npm run build
```

## Configuration

The server requires the following environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `WOFFU_TOKEN` | JWT Bearer token for Woffu API | Yes |
| `WOFFU_USER_ID` | Your Woffu user ID | Yes |
| `WOFFU_BASE_URL` | Woffu instance URL (e.g., `https://mycompany.woffu.com`) | No (defaults to `https://app.woffu.com`) |

### How to get your Woffu JWT Token

1. Log in to your Woffu web portal (e.g., `https://mycompany.woffu.com`)
2. Open browser Developer Tools (F12)
3. Go to the **Application** tab (Chrome) or **Storage** tab (Firefox)
4. In the left panel, expand **Cookies**
5. Click on your Woffu domain (e.g., `https://mycompany.woffu.com`)
6. Find the cookie named **`woffu.token`**
7. Copy the value - this is your `WOFFU_TOKEN`

**Alternative via Console:**
```javascript
document.cookie.split(';').find(c => c.trim().startsWith('woffu.token=')).split('=')[1]
```

**Note**: JWT tokens expire periodically. You may need to refresh the token when it expires.

### How to find your User ID

The User ID is embedded in the JWT token. You can decode it at [jwt.io](https://jwt.io) and look for the `UserId` field in the payload.

Alternatively:
1. In the browser Developer Tools, go to **Network** tab
2. Perform any action in Woffu
3. Look at any API request URL - it often contains your user ID (e.g., `/api/users/1234567/...`)

## Usage

### With Claude Desktop

Add the following to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "woffu": {
      "command": "npx",
      "args": ["-y", "github:iflorit/mcp-woffu-server"],
      "env": {
        "WOFFU_TOKEN": "your-jwt-token-here",
        "WOFFU_USER_ID": "your-user-id",
        "WOFFU_BASE_URL": "https://mycompany.woffu.com"
      }
    }
  }
}
```

### With Claude Code

```bash
claude mcp add woffu --env WOFFU_TOKEN=your-token --env WOFFU_USER_ID=your-id --env WOFFU_BASE_URL=https://mycompany.woffu.com -- npx -y github:iflorit/mcp-woffu-server
```

Or add to your `.claude.json`:

```json
{
  "mcpServers": {
    "woffu": {
      "command": "npx",
      "args": ["-y", "github:iflorit/mcp-woffu-server"],
      "env": {
        "WOFFU_TOKEN": "your-jwt-token-here",
        "WOFFU_USER_ID": "your-user-id",
        "WOFFU_BASE_URL": "https://mycompany.woffu.com"
      }
    }
  }
}
```

### Running the Server Directly

```bash
# With environment variables
export WOFFU_TOKEN="your-token"
export WOFFU_USER_ID="your-user-id"
export WOFFU_BASE_URL="https://mycompany.woffu.com"

# Run the server
npx github:iflorit/mcp-woffu-server
```

## Available Tools

### `woffu_clock_in`

Clock in to start your workday.

**Parameters**: None

**Example response**:
```json
{
  "status": "success",
  "action": "clock_in",
  "timestamp": "2024-01-15T09:00:00",
  "signEventId": "12345"
}
```

### `woffu_clock_out`

Clock out to end your workday.

**Parameters**: None

**Example response**:
```json
{
  "status": "success",
  "action": "clock_out",
  "timestamp": "2024-01-15T18:00:00",
  "signEventId": "12346"
}
```

### `woffu_status`

Get today's work status including schedule and hours worked.

**Parameters**: None

**Returns**: Detailed workday information including:
- Current clock status
- Hours worked today
- Expected hours
- Break times

### `woffu_month_summary`

Get a summary of worked hours for a specific month.

**Parameters**:
- `year` (optional): Year (defaults to current year)
- `month` (optional): Month 1-12 (defaults to current month)

**Returns**: Monthly presence summary with daily breakdowns.

### `woffu_week_summary`

Get a weekly summary of worked hours.

**Parameters**:
- `date` (optional): Any date within the desired week in YYYY-MM-DD format

**Returns**: Weekly presence summary with daily breakdowns.

### `woffu_day_detail`

Get detailed information for a specific day.

**Parameters**:
- `date` (optional): Date in YYYY-MM-DD format (defaults to today)

**Returns**: Detailed day information including all clock events.

### `woffu_pending_days`

Get days without completed hours.

**Parameters**:
- `year` (optional): Year (defaults to current year)
- `month` (optional): Month 1-12 (defaults to current month)

**Returns**: List of workdays where no hours have been logged.

### `woffu_schedule`

Get the user's assigned work schedule.

**Parameters**: None

**Returns**: Schedule information including work hours and office details.

### `woffu_complete_day`

Complete or edit time entries for a past day.

**Parameters**:
- `date`: Date in YYYY-MM-DD format
- `slots`: List of time slots with `in_time` and `out_time` (HH:MM format)
- `confirm` (optional, default `false`): confirm (accept) the day right after filling it. Confirmation requires registered time unless forced.

**Example**:
```json
{
  "date": "2024-01-10",
  "slots": [
    {"in_time": "09:00", "out_time": "14:00"},
    {"in_time": "15:00", "out_time": "18:00"}
  ]
}
```

### `woffu_confirm_day`

Confirm (accept) one or more workday diaries, marking the day's records as reviewed by the employee. Already-confirmed days are skipped.

Refuses days without registered time unless `force: true`.

**Parameters**:
- `dates`: List of dates in YYYY-MM-DD format
- `force` (optional, default `false`): confirm even with no time registered

**Example**:
```json
{
  "dates": ["2024-01-10", "2024-01-11"]
}
```

### `woffu_unconfirm_day`

Unconfirm (revert acceptance of) one or more workday diaries, unlocking them for editing again. Confirmed days are locked: `woffu_complete_day` refuses them until unconfirmed.

**Parameters**:
- `dates`: List of dates in YYYY-MM-DD format

## Example Conversations with Claude

> "Clock me in to Woffu"

> "What's my work status for today?"

> "Show me my hours for November 2024"

> "I forgot to clock in yesterday. Can you fill in 9:00-14:00 and 15:00-18:00 for 2024-01-14?"

> "Show me my pending days this month"

## Development

### Setup

```bash
git clone https://github.com/iflorit/mcp-woffu-server.git
cd mcp-woffu-server
npm install
```

### Building

```bash
npm run build
```

### Running in development

```bash
npm run dev
```

## Security Notes

- **Never commit your JWT token** to version control
- Use environment variables or secure secret management
- JWT tokens expire - refresh the token from the `woffu.token` cookie when needed
- The server only accepts local connections by default

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- Built with the [Model Context Protocol](https://modelcontextprotocol.io/) SDK
- Integrates with [Woffu](https://www.woffu.com/) time tracking
