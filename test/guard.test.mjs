import { test } from "node:test";
import assert from "node:assert/strict";
import { checkDayReady, signedHours } from "../dist/guard.js";

const slot = (i, o, id) => ({
  in: { signId: id, time: i },
  out: { signId: id, time: o },
});
const wd = (workingTime, ...slots) => ({
  diarySummaryWorkday: { workingTime },
  signSlots: slots,
});

test("empty day: schedule placeholders (signId 0) are not signs", () => {
  // Captured 2026-09-08 after a PUT that returned 204 but persisted nothing.
  const c = checkDayReady(wd(28800, slot("08:00:00", "14:00:00", 0), slot("15:00:00", "17:00:00", 0)));
  assert.equal(c.ok, false);
  assert.equal(c.signed_hours, 0);
  assert.equal(c.slot_count, 0);
  assert.match(c.reasons.join(";"), /no persisted signs/);
});

test("8h in 4 slots (two zero-length) is not compacted", () => {
  // Captured 2026-09-07.
  const c = checkDayReady(
    wd(28800,
      slot("08:00:00", "14:00:00", 1), slot("15:00:00", "17:00:00", 2),
      slot("17:00:00", "17:00:00", 3), slot("17:00:00", "17:00:00", 4))
  );
  assert.equal(c.ok, false);
  assert.equal(c.signed_hours, 8);
  assert.equal(c.slot_count, 4);
  assert.match(c.reasons.join(";"), /4 slots.*at most 2/);
});

test("8h in 2 slots is ready", () => {
  const c = checkDayReady(wd(28800, slot("08:00:00", "14:00:00", 1), slot("15:00:00", "17:00:00", 2)));
  assert.deepEqual(c, {
    ok: true, signed_hours: 8, required_hours: 8, slot_count: 2,
    slots: [{ in: "08:00:00", out: "14:00:00" }, { in: "15:00:00", out: "17:00:00" }],
    reasons: [],
  });
});

test("fewer hours than the schedule is rejected", () => {
  const c = checkDayReady(wd(28800, slot("08:00:00", "14:00:00", 1)));
  assert.equal(c.ok, false);
  assert.match(c.reasons.join(";"), /only 6h signed, schedule requires 8h/);
});

test("required hours follow the day's schedule (6h Friday)", () => {
  const c = checkDayReady(wd(21600, slot("09:00:00", "15:00:00", 1)));
  assert.equal(c.ok, true);
  assert.equal(c.required_hours, 6);
});

test("signedHours ignores unpaired/placeholder slots", () => {
  const s = signedHours(wd(28800, { in: { signId: 5, time: "08:00:00" }, out: { signId: 0, time: "14:00:00" } }));
  assert.equal(s.hours, 6); // in is persisted; out time is the placeholder still counted
});
