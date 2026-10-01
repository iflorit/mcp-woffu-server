/** Readiness guard shared by woffu_complete_day and woffu_confirm_day.
 * Works purely on the workday/slots payload (persisted signs), which is the
 * source of truth: the presence summary lags behind an async projection. */
export interface WorkdayData {
    diarySummaryWorkday?: Record<string, unknown>;
    signSlots?: Array<{
        in?: {
            signId?: number;
            time?: string;
        };
        out?: {
            signId?: number;
            time?: string;
        };
    }>;
}
export declare const MAX_SLOTS = 2;
/** The schedule is a MINIMUM: a day may fall short by at most this many
 * seconds and still count as complete, and may exceed it without limit.
 * Live signs land with seconds (08:00:24) and the agent rounds each end up to
 * the next 5-minute mark, so a day never hits the exact second; demanding
 * exactness blocked otherwise fine days. Working longer is never trimmed. */
export declare const TOLERANCE_SECONDS: number;
/** Human-readable duration, seconds included: a "8h vs 8h" message hid the
 * one-second shortfall that let 08:00:24-16:00:23 confirm. */
export declare function hms(seconds: number): string;
export declare function toMinutes(t: string): number;
/** Seconds since midnight. Woffu counts seconds: a live clock-in at 08:00:24
 * with a clock-out at 16:00:23 is 7h59m59s, not 8h, and rounding to minutes
 * reported such a day as complete. */
export declare function toSeconds(t: string): number;
/** Worked hours computed from persisted signs: both in and out must have
 * signId > 0. A pair with a placeholder out (signId 0) is an open clock-in
 * whose out is the schedule template, not a persisted sign. Zero-length
 * pairs are surplus signs collapsed onto a block end (the API cannot delete
 * signs); they carry no time and are not counted as slots. */
export declare function signedHours(wd: WorkdayData): {
    hours: number;
    slots: Array<{
        in: string;
        out: string;
    }>;
};
export interface DayCheck {
    ok: boolean;
    signed_hours: number;
    required_hours: number;
    slot_count: number;
    slots: Array<{
        in: string;
        out: string;
    }>;
    reasons: string[];
}
/** A day is ready to confirm when its persisted signs cover the scheduled
 * hours and are compacted into at most MAX_SLOTS slots. */
export declare function checkDayReady(wd: WorkdayData): DayCheck;
/** Pre-flight for a slot write: refuse before touching Woffu unless the
 * requested slots would leave the day complete, and unless the day has
 * persisted signs to edit (the slots endpoint cannot create signs). */
export declare function checkWritePlan(wd: WorkdayData, requested: Array<{
    in_time: string;
    out_time: string;
}>): {
    ok: boolean;
    requested_hours: number;
    required_hours: number;
    reasons: string[];
};
//# sourceMappingURL=guard.d.ts.map