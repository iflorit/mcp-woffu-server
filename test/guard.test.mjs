import { test } from "node:test";
import assert from "node:assert/strict";
import { checkDayReady, checkWritePlan, signedHours, hms, toSeconds } from "../dist/guard.js";

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

test("8h in one block plus zero-length leftovers is ready", () => {
  // Captured 2026-09-07: surplus signs cannot be deleted through the API,
  // the only compaction possible is collapsing them onto the block end.
  // Those 0-minute pairs carry no time and must not count as slots.
  const c = checkDayReady(
    wd(28800,
      slot("08:00:00", "16:00:00", 1),
      slot("16:00:00", "16:00:00", 3), slot("16:00:00", "16:00:00", 4))
  );
  assert.equal(c.ok, true);
  assert.equal(c.signed_hours, 8);
  assert.equal(c.slot_count, 1);
  assert.deepEqual(c.slots, [{ in: "08:00:00", out: "16:00:00" }]);
});

test("8h in 3 real slots is not compacted", () => {
  const c = checkDayReady(
    wd(28800,
      slot("08:00:00", "11:00:00", 1), slot("11:00:00", "14:00:00", 2),
      slot("15:00:00", "17:00:00", 3))
  );
  assert.equal(c.ok, false);
  assert.equal(c.slot_count, 3);
  assert.match(c.reasons.join(";"), /3 slots.*at most 2/);
});

test("one block of the scheduled hours is the target shape", () => {
  const c = checkDayReady(wd(28800, slot("08:00:00", "16:00:00", 1)));
  assert.equal(c.ok, true);
  assert.equal(c.slot_count, 1);
  assert.equal(checkDayReady(wd(21600, slot("09:00:00", "15:00:00", 1))).ok, true);
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
  assert.match(c.reasons.join(";"), /6h00m00s signed, schedule requires 8h00m00s/);
});

test("a day within the 5-minute tolerance is ready", () => {
  // Live signs carry seconds (08:00:24-16:00:23 = 7h59m59s) and the agent
  // rounds each end up to the next 5-minute mark, so the day lands close to
  // the schedule rather than exactly on it.
  assert.equal(toSeconds("16:00:23") - toSeconds("08:00:24"), 28799);
  assert.equal(checkDayReady(wd(28800, slot("08:00:24", "16:00:23", 1))).ok, true);
  assert.equal(checkDayReady(wd(28800, slot("08:05:00", "16:01:00", 1))).ok, true);
  assert.equal(checkDayReady(wd(28800, slot("08:00:00", "16:04:00", 1))).ok, true);
});

test("a day outside the 5-minute tolerance is rejected", () => {
  const short = checkDayReady(wd(28800, slot("08:05:00", "15:59:00", 1)));
  assert.equal(short.ok, false);
  assert.match(short.reasons.join(";"), /7h54m00s signed, schedule requires 8h00m00s/);
  assert.match(short.reasons.join(";"), /tolerance 5min/);
  // Symmetric: overshooting by more than 5 minutes is rejected too.
  assert.equal(checkDayReady(wd(28800, slot("08:00:00", "16:06:00", 1))).ok, false);
});

test("write plan accepts slots within tolerance, refuses beyond it", () => {
  const day = wd(28800, slot("08:00:24", "16:00:23", 1));
  assert.equal(
    checkWritePlan(day, [{ in_time: "08:00:24", out_time: "16:00:23" }]).ok,
    true
  );
  const c = checkWritePlan(day, [{ in_time: "08:05:00", out_time: "15:59:00" }]);
  assert.equal(c.ok, false);
  assert.match(c.reasons.join(";"), /total 7h54m00s, schedule requires 8h00m00s/);
});

test("hms formats durations with seconds", () => {
  assert.equal(hms(28800), "8h00m00s");
  assert.equal(hms(28799), "7h59m59s");
  assert.equal(hms(21600), "6h00m00s");
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
  assert.match(c.reasons.join(";"), /total 6h00m00s, schedule requires 8h00m00s/);
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
