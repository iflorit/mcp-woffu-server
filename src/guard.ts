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

/** Worked hours computed from persisted signs (signId > 0). */
export function signedHours(wd: WorkdayData): {
  hours: number;
  slots: Array<{ in: string; out: string }>;
} {
  const slots: Array<{ in: string; out: string }> = [];
  let minutes = 0;
  for (const s of wd.signSlots || []) {
    const inT = s.in?.time;
    const outT = s.out?.time;
    if ((s.in?.signId || 0) > 0 && inT && outT) {
      slots.push({ in: inT, out: outT });
      minutes += toMinutes(outT) - toMinutes(inT);
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
