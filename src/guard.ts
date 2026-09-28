/** Readiness guard shared by woffu_complete_day and woffu_confirm_day.
 * Works purely on the workday/slots payload (persisted signs), which is the
 * source of truth: the presence summary lags behind an async projection. */

export interface WorkdayData {
  diarySummaryWorkday?: Record<string, unknown>;
  signSlots?: Array<{
    in?: { signId?: number; time?: string };
    out?: { signId?: number; time?: string };
  }>;
}

export const MAX_SLOTS = 2;

/** Human-readable duration, seconds included: a "8h vs 8h" message hid the
 * one-second shortfall that let 08:00:24-16:00:23 confirm. */
export function hms(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}h${String(m).padStart(2, "0")}m${String(s).padStart(2, "0")}s`;
}

export function toMinutes(t: string): number {
  const [h, m] = t.split(":");
  return parseInt(h) * 60 + parseInt(m);
}

/** Seconds since midnight. Woffu counts seconds: a live clock-in at 08:00:24
 * with a clock-out at 16:00:23 is 7h59m59s, not 8h, and rounding to minutes
 * reported such a day as complete. */
export function toSeconds(t: string): number {
  const [h, m, s] = t.split(":");
  return parseInt(h) * 3600 + parseInt(m) * 60 + (s ? parseInt(s) : 0);
}

/** Worked hours computed from persisted signs: both in and out must have
 * signId > 0. A pair with a placeholder out (signId 0) is an open clock-in
 * whose out is the schedule template, not a persisted sign. Zero-length
 * pairs are surplus signs collapsed onto a block end (the API cannot delete
 * signs); they carry no time and are not counted as slots. */
export function signedHours(wd: WorkdayData): {
  hours: number;
  slots: Array<{ in: string; out: string }>;
} {
  const slots: Array<{ in: string; out: string }> = [];
  let seconds = 0;
  for (const s of wd.signSlots || []) {
    const inT = s.in?.time;
    const outT = s.out?.time;
    if ((s.in?.signId || 0) > 0 && (s.out?.signId || 0) > 0 && inT && outT) {
      const len = toSeconds(outT) - toSeconds(inT);
      if (len <= 0) continue;
      slots.push({ in: inT, out: outT });
      seconds += len;
    }
  }
  return { hours: seconds / 3600, slots };
}

export interface DayCheck {
  ok: boolean;
  signed_hours: number;
  required_hours: number;
  slot_count: number;
  slots: Array<{ in: string; out: string }>;
  reasons: string[];
}

/** A day is ready to confirm when its persisted signs cover the scheduled
 * hours and are compacted into at most MAX_SLOTS slots. */
export function checkDayReady(wd: WorkdayData): DayCheck {
  const signed = signedHours(wd);
  const workingTime = Number(wd.diarySummaryWorkday?.workingTime ?? 0);
  const required = workingTime > 0 ? workingTime / 3600 : 0;
  const reasons: string[] = [];
  // Compare whole seconds: a day short by one second must not pass.
  const signedSec = Math.round(signed.hours * 3600);
  if (required <= 0) {
    reasons.push("no scheduled hours for this day");
  } else if (signedSec < workingTime) {
    reasons.push(
      `only ${hms(signedSec)} signed, schedule requires ${hms(workingTime)}`
    );
  }
  if (signed.slots.length === 0) {
    reasons.push("no persisted signs");
  } else if (signed.slots.length > MAX_SLOTS) {
    reasons.push(
      `${signed.slots.length} slots signed, must be compacted to at most ${MAX_SLOTS}`
    );
  }
  return {
    ok: reasons.length === 0,
    signed_hours: signed.hours,
    required_hours: required,
    slot_count: signed.slots.length,
    slots: signed.slots,
    reasons,
  };
}

/** Pre-flight for a slot write: refuse before touching Woffu unless the
 * requested slots would leave the day complete, and unless the day has
 * persisted signs to edit (the slots endpoint cannot create signs). */
export function checkWritePlan(
  wd: WorkdayData,
  requested: Array<{ in_time: string; out_time: string }>
): { ok: boolean; requested_hours: number; required_hours: number; reasons: string[] } {
  const workingTime = Number(wd.diarySummaryWorkday?.workingTime ?? 0);
  const required = workingTime > 0 ? workingTime / 3600 : 0;
  let sec = 0;
  for (const s of requested) sec += toSeconds(s.out_time) - toSeconds(s.in_time);
  const hours = sec / 3600;
  const reasons: string[] = [];
  if (requested.length > MAX_SLOTS)
    reasons.push(`at most ${MAX_SLOTS} slots per day (got ${requested.length})`);
  if (required <= 0) reasons.push("no scheduled hours for this day");
  else if (sec < workingTime)
    reasons.push(
      `requested slots total ${hms(sec)}, schedule requires ${hms(workingTime)}`
    );
  if (signedHours(wd).slots.length === 0)
    reasons.push(
      "day has no persisted signs; the slots endpoint can only edit existing " +
        "signs, so the write would be silently discarded"
    );
  return { ok: reasons.length === 0, requested_hours: hours, required_hours: required, reasons };
}
