# Waiting for an Ashby form's system fields before filling

Ashby application forms sometimes render their built-in "system" fields (name, e-mail, phone, resume …) a few seconds
late. Filling before they exist loses the values. Two pure functions decide what to wait for and how long.

## system_fields(plan) → list of field objects
plan = {"ats": "...", "fields": [{"key": "...", "status": "...", ...}, ...]}.
Returns, in plan order, the fields whose key starts with "_systemfield_" AND whose status is "ok" or "file" (the runner
fills those). Fields with other statuses ("skip_optional", "needs_user", "check_only") are not waited for. Keys that only
contain "_systemfield_" later in the string do not count. When plan["ats"] is not exactly "ashby" (e.g. "lever",
"greenhouse") the result is an empty list. A plan with no "fields" gives an empty list.

## wait_until(present, keys, timeout, step, clock, sleep) → list of keys still missing
- present(key) → true/false: is that field on the page now.
- Checks every key (in the given order) once immediately. If none are missing, returns [] without sleeping.
- Otherwise, while time remains, calls sleep(step) and checks again. The deadline is clock() at the start + timeout;
  it stops checking as soon as a check happens at or after the deadline, and returns the keys missing in that last check,
  in the original order.
- timeout 0 → exactly one check, no sleep.
- An empty keys list → [] immediately.
