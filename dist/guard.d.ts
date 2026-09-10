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
export declare function toMinutes(t: string): number;
/** Worked hours computed from persisted signs: both in and out must have
 * signId > 0. A pair with a placeholder out (signId 0) is an open clock-in
 * whose out is the schedule template, not a persisted sign. */
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
//# sourceMappingURL=guard.d.ts.map