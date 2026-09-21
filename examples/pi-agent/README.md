# Pi agent example

A dependency-free Python 3 script that keeps every workday signed as **one
block of the scheduled hours** and confirms the day only when the persisted
signs match the schedule exactly. It talks to the Woffu REST API directly, so
it runs on anything with Python 3 (a Raspberry Pi Zero works).

Why it exists: Woffu's slot endpoint can only *edit* signs that already
exist, and `POST /api/svc/signs/signs` always records "now". So the agent has
to create the signs live during the day and reshape them at night. See the
module docstring for the full explanation.

> Unsupported, opt-in example. Unattended clock-in/out and automatic
> confirmation of attendance records may be against your employer's policy or
> local record-keeping rules. Logs and Slack reports contain attendance times;
> keep them private (`chmod 600 .env`, restrict the log directory).

## Setup

```bash
cp .env.example .env   # fill in WOFFU_* (and optionally Slack); never commit it
python3 -m unittest test_woffu_agent.py
```

## Target block per weekday: `schedule.json`

```json
{
  "days": {
    "mon": { "start": "08:00", "hours": 8 },
    "tue": { "start": "08:00", "hours": 8 },
    "wed": { "start": "08:00", "hours": 8 },
    "thu": { "start": "08:00", "hours": 8 },
    "fri": { "start": "09:00", "hours": 6 },
    "sat": null,
    "sun": null
  }
}
```

The file is optional and validated on start-up (unknown day keys, missing
fields or blocks past midnight abort the run). Days omitted or `null` fall
back to the schedule Woffu assigns for that date (its start time plus its
working time), so a shift change in Woffu is picked up without editing
anything. Weekends, holidays, calendar events and absences are always
skipped, whatever this file says.

## Cron

```
0,30 8-21 * * 1-5  /usr/bin/python3 /path/to/woffu_agent.py clock  >> cron.log 2>&1
0 22 * * 1-5       /usr/bin/python3 /path/to/woffu_agent.py fill   >> cron.log 2>&1
0 8 * * 1          /usr/bin/python3 /path/to/woffu_agent.py report >> cron.log 2>&1
```

- `clock`: idempotent tick. Signs in once the scheduled start has passed and
  no sign exists; signs out once the scheduled end has passed and the day is
  open. Missed ticks recover on the next one.
- `fill [YYYY-MM-DD]`: edits the day's signs to `start .. start + workingTime`
  (e.g. 08:00-16:00, or 09:00-15:00 on a 6h day), collapses surplus signs to
  zero length (they cannot be deleted), verifies, and confirms only if the
  hours match. Without a date it sweeps the current month up to today.
- `report`: last week's summary to Slack.

Days that end up with no signs at all cannot be recovered through the API and
are reported for manual fixing in the web UI.
