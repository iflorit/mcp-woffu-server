#!/usr/bin/env node
/**
 * Woffu MCP Server - MCP server for Woffu time tracking.
 *
 * Environment variables:
 *   WOFFU_TOKEN: JWT token from Woffu (required)
 *   WOFFU_USER_ID: User ID from Woffu (required)
 *   WOFFU_BASE_URL: Base URL (default: https://app.woffu.com)
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema, } from "@modelcontextprotocol/sdk/types.js";
function getConfig() {
    return {
        token: process.env.WOFFU_TOKEN || "",
        userId: process.env.WOFFU_USER_ID || "",
        baseUrl: process.env.WOFFU_BASE_URL || "https://app.woffu.com",
    };
}
function validateConfig(config) {
    if (!config.token) {
        return "WOFFU_TOKEN environment variable is not set";
    }
    if (!config.userId) {
        return "WOFFU_USER_ID environment variable is not set";
    }
    return null;
}
function getHeaders(token) {
    return {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
    };
}
// =============================================================================
// Woffu API Functions
// =============================================================================
async function clockIn() {
    const config = getConfig();
    const err = validateConfig(config);
    if (err)
        return { error: err };
    const url = `${config.baseUrl}/api/svc/signs/signs`;
    const payload = { UserId: parseInt(config.userId), signIn: true };
    try {
        const response = await fetch(url, {
            method: "POST",
            headers: getHeaders(config.token),
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            const text = await response.text();
            return { error: `HTTP error: ${response.status}`, details: text };
        }
        const result = (await response.json());
        return {
            status: "success",
            action: "clock_in",
            timestamp: new Date().toISOString(),
            signEventId: result.signEventId,
        };
    }
    catch (e) {
        return { error: `Request failed: ${e}` };
    }
}
async function clockOut() {
    const config = getConfig();
    const err = validateConfig(config);
    if (err)
        return { error: err };
    const url = `${config.baseUrl}/api/svc/signs/signs`;
    const payload = { UserId: parseInt(config.userId), signIn: false };
    try {
        const response = await fetch(url, {
            method: "POST",
            headers: getHeaders(config.token),
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            const text = await response.text();
            return { error: `HTTP error: ${response.status}`, details: text };
        }
        const result = (await response.json());
        return {
            status: "success",
            action: "clock_out",
            timestamp: new Date().toISOString(),
            signEventId: result.signEventId,
        };
    }
    catch (e) {
        return { error: `Request failed: ${e}` };
    }
}
async function getTodayStatus() {
    const config = getConfig();
    const err = validateConfig(config);
    if (err)
        return { error: err };
    const url = `${config.baseUrl}/api/svc/core/users/${config.userId}/diarysummaries/workday`;
    try {
        const response = await fetch(url, {
            method: "GET",
            headers: getHeaders(config.token),
        });
        if (!response.ok) {
            const text = await response.text();
            return { error: `HTTP error: ${response.status}`, details: text };
        }
        return (await response.json());
    }
    catch (e) {
        return { error: `Request failed: ${e}` };
    }
}
async function getMonthSummary(year, month) {
    const config = getConfig();
    const err = validateConfig(config);
    if (err)
        return { error: err };
    const now = new Date();
    year = year || now.getFullYear();
    month = month || now.getMonth() + 1;
    if (month < 1 || month > 12) {
        return { error: "Month must be between 1 and 12" };
    }
    const fromDate = `${year}-${month.toString().padStart(2, "0")}-01`;
    const toDate = month === 12
        ? `${year}-12-31`
        : `${year}-${(month + 1).toString().padStart(2, "0")}-01`;
    const url = `${config.baseUrl}/api/svc/core/diariesquery/users/${config.userId}` +
        `/diaries/summary/presence?userId=${config.userId}` +
        `&fromDate=${fromDate}&toDate=${toDate}` +
        `&pageSize=31&includeHourTypes=true&includeNotHourTypes=true&includeDifference=true`;
    try {
        const response = await fetch(url, {
            method: "GET",
            headers: getHeaders(config.token),
        });
        if (!response.ok) {
            const text = await response.text();
            return { error: `HTTP error: ${response.status}`, details: text };
        }
        return (await response.json());
    }
    catch (e) {
        return { error: `Request failed: ${e}` };
    }
}
async function getWeekSummary(date) {
    const config = getConfig();
    const err = validateConfig(config);
    if (err)
        return { error: err };
    let targetDate;
    if (date) {
        targetDate = new Date(date);
        if (isNaN(targetDate.getTime())) {
            return { error: "Date must be in YYYY-MM-DD format" };
        }
    }
    else {
        targetDate = new Date();
    }
    const daysSinceMonday = (targetDate.getDay() + 6) % 7;
    const monday = new Date(targetDate);
    monday.setDate(targetDate.getDate() - daysSinceMonday);
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    const fromDate = monday.toISOString().split("T")[0];
    const toDate = sunday.toISOString().split("T")[0];
    const url = `${config.baseUrl}/api/svc/core/diariesquery/users/${config.userId}` +
        `/diaries/summary/presence?userId=${config.userId}` +
        `&fromDate=${fromDate}&toDate=${toDate}` +
        `&pageSize=7&includeHourTypes=true&includeNotHourTypes=true&includeDifference=true`;
    try {
        const response = await fetch(url, {
            method: "GET",
            headers: getHeaders(config.token),
        });
        if (!response.ok) {
            const text = await response.text();
            return { error: `HTTP error: ${response.status}`, details: text };
        }
        const data = (await response.json());
        const weekNumber = getWeekNumber(targetDate);
        return {
            ...data,
            week_info: {
                from_date: fromDate,
                to_date: toDate,
                week_number: weekNumber,
            },
        };
    }
    catch (e) {
        return { error: `Request failed: ${e}` };
    }
}
function getWeekNumber(date) {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}
async function getDayDetail(date) {
    const config = getConfig();
    const err = validateConfig(config);
    if (err)
        return { error: err };
    if (date) {
        const parsed = new Date(date);
        if (isNaN(parsed.getTime())) {
            return { error: "Date must be in YYYY-MM-DD format" };
        }
    }
    else {
        date = new Date().toISOString().split("T")[0];
    }
    const url = `${config.baseUrl}/api/svc/core/diariesquery/users/${config.userId}` +
        `/diaries/summary/presence?userId=${config.userId}` +
        `&fromDate=${date}&toDate=${date}` +
        `&pageSize=1&includeHourTypes=true&includeNotHourTypes=true&includeDifference=true`;
    try {
        const response = await fetch(url, {
            method: "GET",
            headers: getHeaders(config.token),
        });
        if (!response.ok) {
            const text = await response.text();
            return { error: `HTTP error: ${response.status}`, details: text };
        }
        const summaryData = await response.json();
        const signsUrl = `${config.baseUrl}/api/svc/signs/slots?userId=${config.userId}&date=${date}`;
        const signsResponse = await fetch(signsUrl, {
            method: "GET",
            headers: getHeaders(config.token),
        });
        const result = { date, summary: summaryData };
        if (signsResponse.ok) {
            result.signs = await signsResponse.json();
        }
        return result;
    }
    catch (e) {
        return { error: `Request failed: ${e}` };
    }
}
async function fetchDiaries(config, fromDate, toDate) {
    const rangeDays = Math.round((new Date(toDate).getTime() - new Date(fromDate).getTime()) / 86400000) + 1;
    const pageSize = Math.max(31, rangeDays);
    const url = `${config.baseUrl}/api/svc/core/diariesquery/users/${config.userId}` +
        `/diaries/summary/presence?userId=${config.userId}` +
        `&fromDate=${fromDate}&toDate=${toDate}` +
        `&pageSize=${pageSize}&includeHourTypes=true&includeNotHourTypes=true&includeDifference=true`;
    const response = await fetch(url, {
        method: "GET",
        headers: getHeaders(config.token),
    });
    if (!response.ok) {
        const text = await response.text();
        return { error: `HTTP error: ${response.status}`, details: text };
    }
    const data = (await response.json());
    return data.diaries || [];
}
async function confirmDays(dates, force = false) {
    const config = getConfig();
    const err = validateConfig(config);
    if (err)
        return { error: err };
    if (!dates || dates.length === 0) {
        return { error: "At least one date is required" };
    }
    for (const date of dates) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || isNaN(new Date(date).getTime())) {
            return { error: `Invalid date: ${date}. Use YYYY-MM-DD format.` };
        }
    }
    const sorted = [...dates].sort();
    const fromDate = sorted[0];
    const toDate = sorted[sorted.length - 1];
    try {
        const diaries = await fetchDiaries(config, fromDate, toDate);
        if (!Array.isArray(diaries))
            return diaries;
        const wanted = new Set(dates);
        const toConfirm = [];
        const alreadyConfirmed = [];
        const noTimeRegistered = [];
        const notFound = new Set(dates);
        for (const day of diaries) {
            const dayDate = (day.date || "").substring(0, 10);
            if (!wanted.has(dayDate))
                continue;
            notFound.delete(dayDate);
            const workedHours = parseFloat(day.workedTimeFormatted?.values?.[0] || "0");
            if (day.accepted === true) {
                alreadyConfirmed.push(dayDate);
            }
            else if (workedHours <= 0 && !force) {
                noTimeRegistered.push(dayDate);
            }
            else if (day.diarySummaryId) {
                toConfirm.push({ date: dayDate, diarySummaryId: day.diarySummaryId });
            }
        }
        if (notFound.size > 0) {
            return {
                error: `No diary found for dates: ${[...notFound].join(", ")}`,
            };
        }
        if (noTimeRegistered.length > 0 && toConfirm.length === 0) {
            return {
                error: `No time registered on: ${noTimeRegistered.join(", ")}. ` +
                    `Fill the day first (woffu_complete_day) or retry with force=true.`,
                already_confirmed: alreadyConfirmed,
            };
        }
        if (toConfirm.length === 0) {
            return {
                status: "success",
                action: "confirm_days",
                confirmed: [],
                already_confirmed: alreadyConfirmed,
                skipped_no_time: noTimeRegistered,
                message: "Nothing to confirm",
            };
        }
        const url = `${config.baseUrl}/api/svc/core/diariesquery/users/diarysummaries/confirm`;
        const response = await fetch(url, {
            method: "PUT",
            headers: getHeaders(config.token),
            body: JSON.stringify({
                diarySummaryIds: toConfirm.map((d) => d.diarySummaryId),
            }),
        });
        if (!response.ok) {
            const text = await response.text();
            return { error: `HTTP error: ${response.status}`, details: text };
        }
        return {
            status: "success",
            action: "confirm_days",
            confirmed: toConfirm.map((d) => d.date),
            already_confirmed: alreadyConfirmed,
            skipped_no_time: noTimeRegistered,
            ...(noTimeRegistered.length > 0 && {
                warning: `NOT confirmed (no time registered): ${noTimeRegistered.join(", ")}. ` +
                    `Fill them first or use force=true.`,
            }),
        };
    }
    catch (e) {
        return { error: `Request failed: ${e}` };
    }
}
async function unconfirmDays(dates) {
    const config = getConfig();
    const err = validateConfig(config);
    if (err)
        return { error: err };
    if (!dates || dates.length === 0) {
        return { error: "At least one date is required" };
    }
    for (const date of dates) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || isNaN(new Date(date).getTime())) {
            return { error: `Invalid date: ${date}. Use YYYY-MM-DD format.` };
        }
    }
    const url = `${config.baseUrl}/api/svc/core/users/diarysummaries/accept`;
    try {
        const response = await fetch(url, {
            method: "PUT",
            headers: getHeaders(config.token),
            body: JSON.stringify({
                acceptDiarySummaries: dates.map((date) => ({
                    userId: parseInt(config.userId),
                    date,
                    accepted: false,
                })),
            }),
        });
        if (!response.ok) {
            const text = await response.text();
            return { error: `HTTP error: ${response.status}`, details: text };
        }
        return {
            status: "success",
            action: "unconfirm_days",
            unconfirmed: dates,
        };
    }
    catch (e) {
        return { error: `Request failed: ${e}` };
    }
}
async function getPendingDays(year, month) {
    const config = getConfig();
    const err = validateConfig(config);
    if (err)
        return { error: err };
    const now = new Date();
    year = year || now.getFullYear();
    month = month || now.getMonth() + 1;
    if (month < 1 || month > 12) {
        return { error: "Month must be between 1 and 12" };
    }
    const fromDate = `${year}-${month.toString().padStart(2, "0")}-01`;
    const toDate = month === 12
        ? `${year}-12-31`
        : `${year}-${(month + 1).toString().padStart(2, "0")}-01`;
    const url = `${config.baseUrl}/api/svc/core/diariesquery/users/${config.userId}` +
        `/diaries/summary/presence?userId=${config.userId}` +
        `&fromDate=${fromDate}&toDate=${toDate}` +
        `&pageSize=31&includeHourTypes=true&includeNotHourTypes=true&includeDifference=true`;
    try {
        const response = await fetch(url, {
            method: "GET",
            headers: getHeaders(config.token),
        });
        if (!response.ok) {
            const text = await response.text();
            return { error: `HTTP error: ${response.status}`, details: text };
        }
        const data = (await response.json());
        const pendingDays = [];
        const today = now.toISOString().split("T")[0];
        for (const day of data.diaries || []) {
            const dayDate = (day.date || "").substring(0, 10);
            const isWorkday = !day.isWeekend && !day.isHoliday;
            const workedHours = parseFloat(day.workedTimeFormatted?.values?.[0] || "0");
            if (isWorkday && workedHours === 0 && dayDate <= today) {
                pendingDays.push({
                    date: dayDate,
                    diary_summary_id: day.diarySummaryId,
                    confirmed: day.accepted === true,
                    schedule: `${day.in || ""}-${day.out || ""}`,
                });
            }
        }
        return {
            year,
            month,
            pending_count: pendingDays.length,
            pending_days: pendingDays,
        };
    }
    catch (e) {
        return { error: `Request failed: ${e}` };
    }
}
async function getSchedule() {
    const config = getConfig();
    const err = validateConfig(config);
    if (err)
        return { error: err };
    const url = `${config.baseUrl}/api/svc/core/users/${config.userId}/diarysummaries/workday`;
    try {
        const response = await fetch(url, {
            method: "GET",
            headers: getHeaders(config.token),
        });
        if (!response.ok) {
            const text = await response.text();
            return { error: `HTTP error: ${response.status}`, details: text };
        }
        const data = (await response.json());
        const schedule = {
            start_time: data.startTime,
            end_time: data.endTime,
            office_name: data.officeName,
            schedule_hours: data.scheduleTime ? data.scheduleTime / 3600 : null,
            timezone: data.timezone,
            flexible_schedule: data.flexibleSchedule,
        };
        const scheduleUrl = `${config.baseUrl}/api/svc/core/users/${config.userId}/schedules`;
        const scheduleResponse = await fetch(scheduleUrl, {
            method: "GET",
            headers: getHeaders(config.token),
        });
        if (scheduleResponse.ok) {
            schedule.detailed_schedule = await scheduleResponse.json();
        }
        return schedule;
    }
    catch (e) {
        return { error: `Request failed: ${e}` };
    }
}
async function completeDay(date, slots, confirm = false, force = false) {
    const config = getConfig();
    const err = validateConfig(config);
    if (err)
        return { error: err };
    const parsed = new Date(date);
    if (isNaN(parsed.getTime())) {
        return { error: "Date must be in YYYY-MM-DD format" };
    }
    // Validate: today cannot be filled until after 17:00
    const now = new Date();
    const todayStr = now.toISOString().split("T")[0];
    if (date === todayStr && now.getHours() < 17) {
        return {
            error: `Cannot complete today until after 17:00. Current time: ${now.getHours()}:${now.getMinutes().toString().padStart(2, "0")}`,
        };
    }
    if (!slots || slots.length === 0) {
        return { error: "At least one time slot is required" };
    }
    const diaries = await fetchDiaries(config, date, date);
    if (!Array.isArray(diaries))
        return diaries;
    const diary = diaries.find((d) => (d.date || "").substring(0, 10) === date);
    if (!diary?.diaryId) {
        return { error: `No diary found for date: ${date}` };
    }
    if (!force) {
        const reasons = [];
        if (diary.isWeekend)
            reasons.push("weekend");
        if (diary.isHoliday)
            reasons.push("holiday");
        if (diary.isEvent)
            reasons.push("calendar event");
        if ((diary.absenceEvents?.length || 0) > 0)
            reasons.push("absence/vacation");
        if ((diary.pendingAbsenceEvents?.length || 0) > 0)
            reasons.push("pending absence request");
        if (reasons.length > 0) {
            return {
                error: `Day ${date} is not a regular workday (${reasons.join(", ")}). ` +
                    `Retry with force=true to fill it anyway.`,
            };
        }
    }
    if (diary.accepted === true) {
        return {
            error: `Day ${date} is confirmed and locked for editing. ` +
                `Unconfirm it first with woffu_unconfirm_day.`,
        };
    }
    const diaryId = diary.diaryId;
    const url = `${config.baseUrl}/api/diaries/${diaryId}/workday/slots/self`;
    const formattedSlots = [];
    const makeSign = (time, signIn) => ({
        signId: 0,
        userId: parseInt(config.userId),
        date: `${date}T${time}`,
        trueDate: `${date}T${time}`,
        signIn,
        time,
        valueTime: time,
        shortTime: time,
        shortTrueTime: time,
        shortValueTime: time,
        utcTime: `${time} +0`,
        signType: 3,
        signStatus: 0,
        deviceType: 0,
        deleted: false,
    });
    for (let i = 0; i < slots.length; i++) {
        const slot = slots[i];
        const inTime = slot.in_time || "08:00";
        const outTime = slot.out_time || "17:00";
        const inParts = inTime.split(":");
        const outParts = outTime.split(":");
        if (inParts.length !== 2 || outParts.length !== 2) {
            return { error: `Invalid time format in slot ${i + 1}. Use HH:MM format.` };
        }
        const inHour = parseInt(inParts[0]);
        const inMin = parseInt(inParts[1]);
        const outHour = parseInt(outParts[0]);
        const outMin = parseInt(outParts[1]);
        if (isNaN(inHour) ||
            isNaN(inMin) ||
            inHour < 0 ||
            inHour > 23 ||
            inMin < 0 ||
            inMin > 59) {
            return { error: `Invalid in_time in slot ${i + 1}` };
        }
        if (isNaN(outHour) ||
            isNaN(outMin) ||
            outHour < 0 ||
            outHour > 23 ||
            outMin < 0 ||
            outMin > 59) {
            return { error: `Invalid out_time in slot ${i + 1}` };
        }
        const totalMin = outHour * 60 + outMin - (inHour * 60 + inMin);
        if (totalMin <= 0) {
            return { error: `out_time must be after in_time in slot ${i + 1}` };
        }
        const inStr = `${inHour.toString().padStart(2, "0")}:${inMin.toString().padStart(2, "0")}:00`;
        const outStr = `${outHour.toString().padStart(2, "0")}:${outMin.toString().padStart(2, "0")}:00`;
        formattedSlots.push({
            in: makeSign(inStr, true),
            out: makeSign(outStr, false),
            motive: null,
        });
    }
    const payload = {
        diaryId,
        date,
        comments: "",
        userId: parseInt(config.userId),
        slots: formattedSlots,
    };
    try {
        const response = await fetch(url, {
            method: "PUT",
            headers: getHeaders(config.token),
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            const text = await response.text();
            return { error: `HTTP error: ${response.status}`, details: text };
        }
        const result = {
            status: "success",
            action: "complete_day",
            date,
            slots_count: formattedSlots.length,
            note: "Woffu persists and recalculates asynchronously. Verify with " +
                "woffu_day_detail; closed periods (e.g. past months) may silently " +
                "discard the write.",
        };
        if (confirm) {
            // Force: worked time is recalculated asynchronously, so the freshly
            // written slots may not be reflected yet.
            result.confirmation = await confirmDays([date], true);
        }
        return result;
    }
    catch (e) {
        return { error: `Request failed: ${e}` };
    }
}
// =============================================================================
// MCP Server
// =============================================================================
const TOOLS = [
    {
        name: "woffu_clock_in",
        description: "Clock in (fichar entrada) to Woffu. Use when user wants to start workday.",
        inputSchema: { type: "object", properties: {}, required: [] },
    },
    {
        name: "woffu_clock_out",
        description: "Clock out (fichar salida) from Woffu. Use when user wants to end workday.",
        inputSchema: { type: "object", properties: {}, required: [] },
    },
    {
        name: "woffu_status",
        description: "Get today's work status: hours worked, schedule, clock state.",
        inputSchema: { type: "object", properties: {}, required: [] },
    },
    {
        name: "woffu_month_summary",
        description: "Get monthly summary of worked hours with daily breakdowns.",
        inputSchema: {
            type: "object",
            properties: {
                year: { type: "integer", description: "Year (default: current)" },
                month: {
                    type: "integer",
                    description: "Month 1-12 (default: current)",
                    minimum: 1,
                    maximum: 12,
                },
            },
            required: [],
        },
    },
    {
        name: "woffu_week_summary",
        description: "Get weekly summary of worked hours.",
        inputSchema: {
            type: "object",
            properties: {
                date: {
                    type: "string",
                    description: "Any date in the week (YYYY-MM-DD). Default: current week.",
                },
            },
            required: [],
        },
    },
    {
        name: "woffu_day_detail",
        description: "Get detailed info for a specific day including all clock events.",
        inputSchema: {
            type: "object",
            properties: {
                date: { type: "string", description: "Date (YYYY-MM-DD). Default: today." },
            },
            required: [],
        },
    },
    {
        name: "woffu_pending_days",
        description: "Get workdays without logged hours (pending days).",
        inputSchema: {
            type: "object",
            properties: {
                year: { type: "integer", description: "Year (default: current)" },
                month: {
                    type: "integer",
                    description: "Month 1-12 (default: current)",
                    minimum: 1,
                    maximum: 12,
                },
            },
            required: [],
        },
    },
    {
        name: "woffu_schedule",
        description: "Get the user's assigned work schedule.",
        inputSchema: { type: "object", properties: {}, required: [] },
    },
    {
        name: "woffu_complete_day",
        description: "Fill time entries for a past day. Cannot be used for today until after 17:00.",
        inputSchema: {
            type: "object",
            properties: {
                date: { type: "string", description: "Date (YYYY-MM-DD)" },
                slots: {
                    type: "array",
                    description: "Time slots: [{in_time: 'HH:MM', out_time: 'HH:MM'}, ...]",
                    items: {
                        type: "object",
                        properties: {
                            in_time: { type: "string", description: "Clock in (HH:MM)" },
                            out_time: { type: "string", description: "Clock out (HH:MM)" },
                        },
                        required: ["in_time", "out_time"],
                    },
                },
                confirm: {
                    type: "boolean",
                    description: "Confirm (accept) the day after filling it. Default: false.",
                    default: false,
                },
                force: {
                    type: "boolean",
                    description: "Fill even if the day is a weekend, holiday, event, or has " +
                        "absences/vacations. Default: false.",
                    default: false,
                },
            },
            required: ["date", "slots"],
        },
    },
    {
        name: "woffu_confirm_day",
        description: "Confirm (confirmar) one or more workday diaries in Woffu. Marks the day's " +
            "time records as reviewed/accepted by the employee. Days already confirmed are skipped.",
        inputSchema: {
            type: "object",
            properties: {
                dates: {
                    type: "array",
                    description: "Dates to confirm (YYYY-MM-DD)",
                    items: { type: "string" },
                    minItems: 1,
                },
                force: {
                    type: "boolean",
                    description: "Confirm even if the day has no time registered. Default: false.",
                    default: false,
                },
            },
            required: ["dates"],
        },
    },
    {
        name: "woffu_unconfirm_day",
        description: "Unconfirm (revert acceptance of) one or more workday diaries in Woffu, " +
            "unlocking them for editing again.",
        inputSchema: {
            type: "object",
            properties: {
                dates: {
                    type: "array",
                    description: "Dates to unconfirm (YYYY-MM-DD)",
                    items: { type: "string" },
                    minItems: 1,
                },
            },
            required: ["dates"],
        },
    },
];
const server = new Server({
    name: "woffu",
    version: "0.1.0",
}, {
    capabilities: {
        tools: {},
    },
});
server.setRequestHandler(ListToolsRequestSchema, async () => {
    return { tools: TOOLS };
});
server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    let result;
    switch (name) {
        case "woffu_clock_in":
            result = await clockIn();
            break;
        case "woffu_clock_out":
            result = await clockOut();
            break;
        case "woffu_status":
            result = await getTodayStatus();
            break;
        case "woffu_month_summary":
            result = await getMonthSummary(args?.year, args?.month);
            break;
        case "woffu_week_summary":
            result = await getWeekSummary(args?.date);
            break;
        case "woffu_day_detail":
            result = await getDayDetail(args?.date);
            break;
        case "woffu_pending_days":
            result = await getPendingDays(args?.year, args?.month);
            break;
        case "woffu_schedule":
            result = await getSchedule();
            break;
        case "woffu_complete_day":
            result = await completeDay(args?.date || "", args?.slots || [], args?.confirm === true, args?.force === true);
            break;
        case "woffu_confirm_day":
            result = await confirmDays(args?.dates || [], args?.force === true);
            break;
        case "woffu_unconfirm_day":
            result = await unconfirmDays(args?.dates || []);
            break;
        default:
            result = { error: `Unknown tool: ${name}` };
    }
    return {
        content: [
            {
                type: "text",
                text: JSON.stringify(result, null, 2),
            },
        ],
    };
});
async function main() {
    const config = getConfig();
    const err = validateConfig(config);
    if (err) {
        console.error(`Config warning: ${err}`);
    }
    else {
        console.error(`Woffu MCP Server ready (${config.baseUrl})`);
    }
    const transport = new StdioServerTransport();
    await server.connect(transport);
}
main().catch(console.error);
//# sourceMappingURL=index.js.map