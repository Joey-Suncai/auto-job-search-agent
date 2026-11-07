# Gate: keep the last verdict when a JD cannot be read (JSA-054, Joey 2026-10-31: 「保留上一次的结论」)

The gate re-checks a job row. Each check produces a result: verdict v ∈ {Eligible, Review, Ineligible, Closed, Unverified}
and a list of codes (e.g. NO_SPONSORSHIP, UNREADABLE, FETCH_ERROR, BACHELORS_WORDING, CLOSED). Verdict words:
Eligible → 可投, Review → 待核实, Ineligible → 不可投, Closed → 已关闭, Unverified → 待核实.

A result is a **read failure** when its codes contain UNREADABLE or FETCH_ERROR. Any other result is a **successful read**
(including Closed, and including Review for reasons such as BACHELORS_WORDING or NO_TEXT).

The row before the check may have: elig (verdict), elig_reason, elig_codes (comma-separated), elig_evidence, elig_key,
elig_checked (date of the last check), elig_read_on (date of the last successful read).
The row's **previous read was successful** when it has an elig_checked date and its elig_codes contain neither
UNREADABLE nor FETCH_ERROR.

Rules for one row, today = the check date:
1. Successful read → the row takes the new result: elig = the verdict word, elig_codes = the new codes, elig_evidence and
   elig_key = the new ones, elig_checked = today, elig_read_on = today, and there is no elig_read_fail.
2. Read failure and the previous read was successful → the row KEEPS elig, elig_codes, elig_evidence and elig_key from
   before; elig_checked = today; elig_read_on = the previous elig_read_on if it had one, else the previous elig_checked;
   elig_read_fail = today; elig_reason = the previous reason followed by "（" + elig_read_on + " 读到的 JD；" + today + " 读不到）".
   If the previous reason already ends with such a bracket note, that note is replaced, not added twice.
3. Read failure and the previous read was not successful (or there was no previous check) → the row takes the new
   result as in rule 1 (elig 待核实, the failure codes), except that elig_read_on is not set or changed, and elig_read_fail = today.
4. (JSA-084) Read failure and the row's own `location` field is clearly outside the U.S. (a foreign country, a foreign city
   such as "Abu Dhabi", "Doha", "Toronto", or a region such as "Europe"; a U.S. state / city or "Remote" is not) → this rule
   wins over rules 2 and 3: elig = 不可投, elig_codes = "NON_US", elig_evidence = the location, elig_reason = "不在美国",
   elig_checked = today, elig_read_fail = today, elig_read_on is not set or changed. A successful read is always rule 1,
   whatever the location.
