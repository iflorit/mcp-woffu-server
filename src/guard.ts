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

export function toMinutes(t: string): number {
  const [h, m] = t.split(":");
  return parseInt(h) * 60 + parseInt(m);
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
  let minutes = 0;
  for (const s of wd.signSlots || []) {
    const inT = s.in?.time;
    const outT = s.out?.time;
    if ((s.in?.signId || 0) > 0 && (s.out?.signId || 0) > 0 && inT && outT) {
      const len = toMinutes(outT) - toMinutes(inT);
      if (len <= 0) continue;
      slots.push({ in: inT, out: outT });
      minutes += len;
    }
  }
  return { hours: minutes / 60, slots };
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
  if (required <= 0) {
    reasons.push("no scheduled hours for this day");
  } else if (signed.hours + 1e-9 < required) {
    reasons.push(`only ${signed.hours}h signed, schedule requires ${required}h`);
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
  let minutes = 0;
  for (const s of requested) minutes += toMinutes(s.out_time) - toMinutes(s.in_time);
  const hours = minutes / 60;
  const reasons: string[] = [];
  if (requested.length > MAX_SLOTS)
    reasons.push(`at most ${MAX_SLOTS} slots per day (got ${requested.length})`);
  if (required <= 0) reasons.push("no scheduled hours for this day");
  else if (hours + 1e-9 < required)
    reasons.push(`requested slots total ${hours}h, schedule requires ${required}h`);
  if (signedHours(wd).slots.length === 0)
    reasons.push(
      "day has no persisted signs; the slots endpoint can only edit existing " +
        "signs, so the write would be silently discarded"
    );
  return { ok: reasons.length === 0, requested_hours: hours, required_hours: required, reasons };
}
