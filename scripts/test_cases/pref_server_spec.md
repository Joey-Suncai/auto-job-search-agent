# Dashboard 👍 / 👎 write endpoint — request validation (JSA-101)

A localhost server receives one HTTP request from the dashboard page and decides whether it is a valid preference
request. Inputs: method (string), path (string, may carry a query string), headers (object with lower-case names; a
missing header is absent), body (string, UTF-8). Output: [200, {"id": ..., "pref": ...}] when valid, otherwise
[code, {"error": message}].

Checks, in this order (the first that fails decides the answer), with exactly these codes and messages:
1. The host header must be "localhost" or "127.0.0.1", optionally followed by ":" and a port of 1–5 digits
   (anything else, or no host header) → 421 "bad host"
2. The path without its query string must be exactly "/pref" → 404 "unknown path"
3. The method must be "POST" → 405 "POST only"
4. The origin header must be absent, the literal "null", or "http://localhost" / "http://127.0.0.1" optionally with
   ":port" (1–5 digits) and nothing else (no path, no https, no other host) → 403 "origin not allowed"
5. The x-jsa-pref header must be exactly "1" → 403 "missing X-JSA-Pref header"
6. The content-type header must start with "application/json" (case-insensitive; parameters like "; charset=utf-8"
   are fine) → 415 "Content-Type must be application/json"
7. The body must be at most 1024 bytes → 413 "body too large"
8. The body must parse as JSON → 400 "body is not JSON"
9. It must be a JSON object whose keys are exactly "id" and "pref" (no more, no fewer) → 400 "body must be a JSON object {id, pref}"
10. id must be a string: "J" followed by 4 to 6 digits, nothing else → 400 "bad id"
11. pref must be one of "up", "down", "clear" (exact, lower case) → 400 "pref must be up, down or clear"
Otherwise → [200, {"id": id, "pref": pref}].

# Applying a preference (same code for the CLI and the endpoint)

Given a jobs table (rows with id, company, title and other fields), a list of ids and pref:
- pref "up" sets joey_pref = "up" and joey_pref_on = today's date (YYYY-MM-DD) on each id; "down" likewise with "down";
  "clear" removes both fields (a row without them stays without them).
- If any id is not in the table, nothing is written (table and log unchanged) and the unknown ids are reported.
- Otherwise the table is saved (and re-scored: up → value level "top", down → value level "exclude"; clear → the
  rule-based level) and one log line per id is appended: {id, pref, on, title, company, via}.
- Rows other than the given ids are not changed by the preference.
