import { test } from "node:test";
import assert from "node:assert/strict";
import { checkDayReady, checkWritePlan, signedHours } from "../dist/guard.js";

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

test("open clock-in with placeholder out (signId 0) counts no hours", () => {
  // Shape of a day where the person clocked in but never out: Woffu fills
  // the out with the schedule template. Two of these must NOT confirm.
  const open = (i, o) => ({ in: { signId: 5, time: i }, out: { signId: 0, time: o } });
  assert.equal(signedHours(wd(28800, open("08:00:00", "14:00:00"))).hours, 0);
  const c = checkDayReady(wd(28800, open("08:00:00", "14:00:00"), open("15:00:00", "17:00:00")));
  assert.equal(c.ok, false);
  assert.equal(c.signed_hours, 0);
});

const day07 = wd(28800, slot("08:00:00", "14:00:00", 1), slot("15:00:00", "17:00:00", 2));
const req = (...p) => p.map(([i, o]) => ({ in_time: i, out_time: o }));

test("write plan: refuses fewer hours than the schedule before writing", () => {
  const c = checkWritePlan(day07, req(["08:00", "14:00"]));
  assert.equal(c.ok, false);
  assert.match(c.reasons.join(";"), /total 6h, schedule requires 8h/);
});

test("write plan: refuses more than 2 slots", () => {
  const c = checkWritePlan(day07, req(["08:00", "11:00"], ["11:00", "14:00"], ["15:00", "17:00"]));
  assert.equal(c.ok, false);
  assert.match(c.reasons.join(";"), /at most 2 slots/);
});

test("write plan: refuses a day with no persisted signs (write would be dropped)", () => {
  const empty = wd(28800, slot("08:00:00", "14:00:00", 0), slot("15:00:00", "17:00:00", 0));
  const c = checkWritePlan(empty, req(["08:00", "14:00"], ["15:00", "17:00"]));
  assert.equal(c.ok, false);
  assert.match(c.reasons.join(";"), /no persisted signs/);
});

test("write plan: 8h in 2 slots on a day with signs is allowed", () => {
  const c = checkWritePlan(day07, req(["08:00", "14:00"], ["15:00", "17:00"]));
  assert.deepEqual(c, { ok: true, requested_hours: 8, required_hours: 8, reasons: [] });
});
