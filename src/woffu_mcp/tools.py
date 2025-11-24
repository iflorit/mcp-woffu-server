"""
Woffu API Tools - Core functionality for interacting with Woffu time tracking.
"""

import requests
from datetime import datetime, timedelta
from typing import Any

from .config import get_config


def _get_headers() -> dict[str, str]:
    """Get headers for Woffu API requests."""
    config = get_config()
    return {
        "Authorization": f"Bearer {config.token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def clock_in() -> dict[str, Any]:
    """
    Clock in (fichar entrada) to Woffu.

    Returns:
        Dict with status and signEventId if successful, or error details.
    """
    config = get_config()

    validation_error = config.validate()
    if validation_error:
        return {"error": validation_error}

    url = f"{config.base_url}/api/svc/signs/signs"
    payload = {
        "UserId": int(config.user_id),
        "signIn": True,
    }

    try:
        response = requests.post(url, json=payload, headers=_get_headers(), timeout=30)
        response.raise_for_status()

        result = response.json()
        return {
            "status": "success",
            "action": "clock_in",
            "timestamp": datetime.now().isoformat(),
            "signEventId": result.get("signEventId"),
        }
    except requests.exceptions.HTTPError as e:
        return {
            "error": f"HTTP error: {e.response.status_code}",
            "details": e.response.text,
        }
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def clock_out() -> dict[str, Any]:
    """
    Clock out (fichar salida) from Woffu.

    Returns:
        Dict with status and signEventId if successful, or error details.
    """
    config = get_config()

    validation_error = config.validate()
    if validation_error:
        return {"error": validation_error}

    url = f"{config.base_url}/api/svc/signs/signs"
    payload = {
        "UserId": int(config.user_id),
        "signIn": False,
    }

    try:
        response = requests.post(url, json=payload, headers=_get_headers(), timeout=30)
        response.raise_for_status()

        result = response.json()
        return {
            "status": "success",
            "action": "clock_out",
            "timestamp": datetime.now().isoformat(),
            "signEventId": result.get("signEventId"),
        }
    except requests.exceptions.HTTPError as e:
        return {
            "error": f"HTTP error: {e.response.status_code}",
            "details": e.response.text,
        }
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def get_today_status() -> dict[str, Any]:
    """
    Get today's clock status and workday information.

    Returns:
        Dict with today's workday information including hours worked,
        schedule, and current clock status.
    """
    config = get_config()

    validation_error = config.validate()
    if validation_error:
        return {"error": validation_error}

    url = f"{config.base_url}/api/svc/core/users/{config.user_id}/diarysummaries/workday"

    try:
        response = requests.get(url, headers=_get_headers(), timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        return {
            "error": f"HTTP error: {e.response.status_code}",
            "details": e.response.text,
        }
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def get_month_summary(year: int | None = None, month: int | None = None) -> dict[str, Any]:
    """
    Get monthly summary of worked hours.

    Args:
        year: Year (default: current year)
        month: Month 1-12 (default: current month)

    Returns:
        Dict with monthly presence summary including daily breakdowns.
    """
    config = get_config()

    validation_error = config.validate()
    if validation_error:
        return {"error": validation_error}

    now = datetime.now()
    year = year or now.year
    month = month or now.month

    # Validate month
    if not 1 <= month <= 12:
        return {"error": "Month must be between 1 and 12"}

    from_date = f"{year}-{month:02d}-01"

    # Calculate last day of month
    if month == 12:
        to_date = f"{year}-12-31"
    else:
        to_date = f"{year}-{month + 1:02d}-01"

    url = (
        f"{config.base_url}/api/svc/core/diariesquery/users/{config.user_id}"
        f"/diaries/summary/presence?userId={config.user_id}"
        f"&fromDate={from_date}&toDate={to_date}"
        f"&pageSize=31&includeHourTypes=true&includeNotHourTypes=true&includeDifference=true"
    )

    try:
        response = requests.get(url, headers=_get_headers(), timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        return {
            "error": f"HTTP error: {e.response.status_code}",
            "details": e.response.text,
        }
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def complete_day(date: str, slots: list[dict[str, str]], end_time: str = "17:00") -> dict[str, Any]:
    """
    Complete or edit a past day's time slots.

    Args:
        date: Date in YYYY-MM-DD format
        slots: List of time slots, each with:
            - in_time: Start time (HH:MM format)
            - out_time: End time (HH:MM format)
        end_time: Scheduled end time for today validation (default: 17:00)

    Example:
        complete_day("2024-01-15", [
            {"in_time": "09:00", "out_time": "14:00"},
            {"in_time": "15:00", "out_time": "18:00"}
        ])

    Returns:
        Dict with status and number of slots if successful.

    Note:
        Today's date cannot be filled unless current time is past the end_time.
    """
    config = get_config()

    validation_error = config.validate()
    if validation_error:
        return {"error": validation_error}

    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {"error": "Date must be in YYYY-MM-DD format"}

    # Validate: today cannot be filled unless current time > end_time
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    if date == today_str:
        try:
            end_hour, end_min = map(int, end_time.split(":"))
            end_datetime = now.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
            if now < end_datetime:
                return {
                    "error": f"Cannot complete today ({date}) until after scheduled end time ({end_time}). Current time: {now.strftime('%H:%M')}"
                }
        except ValueError:
            pass  # Invalid end_time format, skip validation

    # Validate slots
    if not slots:
        return {"error": "At least one time slot is required"}

    url = f"{config.base_url}/api/svc/core/users/{config.user_id}/diarysummaries/workday/slots/self"

    # Build slots payload
    formatted_slots = []
    timestamp = int(datetime.now().timestamp() * 1000)

    for i, slot in enumerate(slots):
        in_time = slot.get("in_time", "08:00")
        out_time = slot.get("out_time", "17:00")

        # Validate and parse times
        try:
            in_hour, in_min = map(int, in_time.split(":"))
            out_hour, out_min = map(int, out_time.split(":"))
        except (ValueError, AttributeError):
            return {"error": f"Invalid time format in slot {i + 1}. Use HH:MM format."}

        # Validate time values
        if not (0 <= in_hour <= 23 and 0 <= in_min <= 59):
            return {"error": f"Invalid in_time in slot {i + 1}"}
        if not (0 <= out_hour <= 23 and 0 <= out_min <= 59):
            return {"error": f"Invalid out_time in slot {i + 1}"}

        # Calculate total minutes
        total_min = (out_hour * 60 + out_min) - (in_hour * 60 + in_min)
        if total_min <= 0:
            return {"error": f"out_time must be after in_time in slot {i + 1}"}

        slot_data = {
            "id": f"{timestamp}-{i}",
            "in": {
                "signId": 0,
                "userId": int(config.user_id),
                "date": f"{date}T{in_hour:02d}:00:00.000Z",
                "trueDate": f"{date}T{in_hour:02d}:00:00.000Z",
                "signIn": True,
                "ip": None,
                "latitude": None,
                "longitude": None,
                "outside": None,
                "time": f"{in_hour:02d}:{in_min:02d}:00",
                "valueTime": f"{in_hour:02d}:{in_min:02d}:00",
                "shortTime": f"{in_hour:02d}:{in_min:02d}:00",
                "shortTrueTime": f"{in_hour:02d}:{in_min:02d}:00",
                "shortValueTime": f"{in_hour:02d}:{in_min:02d}:00",
                "utcTime": f"{in_hour:02d}:{in_min:02d}:00 +0",
                "code": None,
                "signType": 3,
                "signStatus": 1,
                "signEventId": None,
                "deviceId": None,
                "deviceType": 0,
                "deleted": False,
                "updatedOn": None,
                "requestId": None,
                "agreementEventId": None,
            },
            "out": {
                "signId": 0,
                "userId": int(config.user_id),
                "date": f"{date}T{out_hour:02d}:00:00.000Z",
                "trueDate": f"{date}T{out_hour:02d}:00:00.000Z",
                "signIn": False,
                "ip": None,
                "latitude": None,
                "longitude": None,
                "outside": None,
                "time": f"{out_hour:02d}:{out_min:02d}:00",
                "valueTime": f"{out_hour:02d}:{out_min:02d}:00",
                "shortTime": f"{out_hour:02d}:{out_min:02d}:00",
                "shortTrueTime": f"{out_hour:02d}:{out_min:02d}:00",
                "shortValueTime": f"{out_hour:02d}:{out_min:02d}:00",
                "utcTime": f"{out_hour:02d}:{out_min:02d}:00 +0",
                "code": None,
                "signType": 3,
                "signStatus": 1,
                "signEventId": None,
                "deviceId": None,
                "deviceType": 0,
                "deleted": False,
                "updatedOn": None,
                "requestId": None,
                "agreementEventId": None,
            },
            "motive": None,
            "totalMin": total_min,
        }
        formatted_slots.append(slot_data)

    payload = {
        "date": date,
        "comments": "",
        "userId": int(config.user_id),
        "slots": formatted_slots,
    }

    try:
        response = requests.put(url, json=payload, headers=_get_headers(), timeout=30)
        response.raise_for_status()

        return {
            "status": "success",
            "action": "complete_day",
            "date": date,
            "slots_count": len(formatted_slots),
        }
    except requests.exceptions.HTTPError as e:
        return {
            "error": f"HTTP error: {e.response.status_code}",
            "details": e.response.text,
        }
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def get_week_summary(date: str | None = None) -> dict[str, Any]:
    """
    Get weekly summary of worked hours.

    Args:
        date: Any date within the desired week (YYYY-MM-DD format).
              Defaults to current week.

    Returns:
        Dict with weekly presence summary including daily breakdowns,
        total hours worked, expected hours, and balance.
    """
    config = get_config()

    validation_error = config.validate()
    if validation_error:
        return {"error": validation_error}

    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return {"error": "Date must be in YYYY-MM-DD format"}
    else:
        target_date = datetime.now()

    # Calculate Monday and Sunday
    days_since_monday = target_date.weekday()
    monday = target_date - timedelta(days=days_since_monday)
    sunday = monday + timedelta(days=6)

    from_date = monday.strftime("%Y-%m-%d")
    to_date = sunday.strftime("%Y-%m-%d")

    url = (
        f"{config.base_url}/api/svc/core/diariesquery/users/{config.user_id}"
        f"/diaries/summary/presence?userId={config.user_id}"
        f"&fromDate={from_date}&toDate={to_date}"
        f"&pageSize=7&includeHourTypes=true&includeNotHourTypes=true&includeDifference=true"
    )

    try:
        response = requests.get(url, headers=_get_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()
        data["week_info"] = {
            "from_date": from_date,
            "to_date": to_date,
            "week_number": target_date.isocalendar()[1],
        }
        return data
    except requests.exceptions.HTTPError as e:
        return {"error": f"HTTP error: {e.response.status_code}", "details": e.response.text}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def get_day_detail(date: str | None = None) -> dict[str, Any]:
    """
    Get detailed information for a specific day.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.

    Returns:
        Dict with detailed day information including all clock events,
        breaks, schedule, and time calculations.
    """
    config = get_config()

    validation_error = config.validate()
    if validation_error:
        return {"error": validation_error}

    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return {"error": "Date must be in YYYY-MM-DD format"}
    else:
        date = datetime.now().strftime("%Y-%m-%d")

    url = (
        f"{config.base_url}/api/svc/core/diariesquery/users/{config.user_id}"
        f"/diaries/summary/presence?userId={config.user_id}"
        f"&fromDate={date}&toDate={date}"
        f"&pageSize=1&includeHourTypes=true&includeNotHourTypes=true&includeDifference=true"
    )

    try:
        response = requests.get(url, headers=_get_headers(), timeout=30)
        response.raise_for_status()
        summary_data = response.json()

        signs_url = f"{config.base_url}/api/svc/signs/slots?userId={config.user_id}&date={date}"
        signs_response = requests.get(signs_url, headers=_get_headers(), timeout=30)

        result = {"date": date, "summary": summary_data}
        if signs_response.ok:
            result["signs"] = signs_response.json()

        return result
    except requests.exceptions.HTTPError as e:
        return {"error": f"HTTP error: {e.response.status_code}", "details": e.response.text}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def get_pending_days(year: int | None = None, month: int | None = None) -> dict[str, Any]:
    """
    Get days without completed hours (pending days).

    Args:
        year: Year (default: current year)
        month: Month 1-12 (default: current month)

    Returns:
        Dict with list of pending days that have 0 worked hours
        but were expected working days.
    """
    config = get_config()

    validation_error = config.validate()
    if validation_error:
        return {"error": validation_error}

    now = datetime.now()
    year = year or now.year
    month = month or now.month

    if not 1 <= month <= 12:
        return {"error": "Month must be between 1 and 12"}

    from_date = f"{year}-{month:02d}-01"
    to_date = f"{year}-12-31" if month == 12 else f"{year}-{month + 1:02d}-01"

    url = (
        f"{config.base_url}/api/svc/core/diariesquery/users/{config.user_id}"
        f"/diaries/summary/presence?userId={config.user_id}"
        f"&fromDate={from_date}&toDate={to_date}"
        f"&pageSize=31&includeHourTypes=true&includeNotHourTypes=true&includeDifference=true"
    )

    try:
        response = requests.get(url, headers=_get_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()

        pending_days = []
        today = now.strftime("%Y-%m-%d")

        for day in data.get("Diaries", []):
            day_date = day.get("Date", "")[:10]
            worked_seconds = day.get("WorkedSeconds", 0)
            expected_seconds = day.get("ExpectedSeconds", 0)
            is_workday = expected_seconds > 0

            if is_workday and worked_seconds == 0 and day_date <= today:
                pending_days.append({
                    "date": day_date,
                    "expected_hours": expected_seconds / 3600,
                    "day_type": day.get("DayTypeName", ""),
                })

        return {
            "year": year,
            "month": month,
            "pending_count": len(pending_days),
            "pending_days": pending_days,
        }
    except requests.exceptions.HTTPError as e:
        return {"error": f"HTTP error: {e.response.status_code}", "details": e.response.text}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def get_schedule() -> dict[str, Any]:
    """
    Get the user's assigned work schedule.

    Returns:
        Dict with schedule information including work hours,
        office location, and weekly pattern.
    """
    config = get_config()

    validation_error = config.validate()
    if validation_error:
        return {"error": validation_error}

    url = f"{config.base_url}/api/svc/core/users/{config.user_id}/diarysummaries/workday"

    try:
        response = requests.get(url, headers=_get_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()

        schedule = {
            "start_time": data.get("startTime"),
            "end_time": data.get("endTime"),
            "office_name": data.get("officeName"),
            "office_id": data.get("officeId"),
            "schedule_time_seconds": data.get("scheduleTime"),
            "schedule_hours": data.get("scheduleTime", 0) / 3600 if data.get("scheduleTime") else None,
            "timezone": data.get("timezone"),
            "flexible_schedule": data.get("flexibleSchedule"),
        }

        schedule_url = f"{config.base_url}/api/svc/core/users/{config.user_id}/schedules"
        schedule_response = requests.get(schedule_url, headers=_get_headers(), timeout=30)
        if schedule_response.ok:
            schedule["detailed_schedule"] = schedule_response.json()

        return schedule
    except requests.exceptions.HTTPError as e:
        return {"error": f"HTTP error: {e.response.status_code}", "details": e.response.text}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}