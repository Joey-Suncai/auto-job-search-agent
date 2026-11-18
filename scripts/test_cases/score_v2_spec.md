# score_v2: job priority = value level + chance of an interview (JSA-096, ADR-0006, Joey 2026-11-03 「按这个做」)

`score_row(job)` returns the job with these fields set (nothing else changes): `v_level`, `score`, `tier_orig`, `tier`,
`s_value`, `s_chance`, `s_referral`, `s_timing`, `s_sponsor`, `s_fresh`, `score_version` = "v2". The first time a row is
scored, its previous `score` is copied to `score_v1` (if `score_v1` is not already present).

Role category comes from `role_category(title)` (ai_pm, data_analysis, pm, ai_nonengineering, ai_engineering, data, other).

1. **Target gate.** The row is *on target* only if `level` is "Internship" and the title does not name an off-cycle term
   (fall, spring, winter, autumn, co-op, part-time, year-round, semester — whole words, any case). Off-target rows get
   v_level "off_target".
2. **Value level** (on-target rows), first match wins:
   - "exclude" if `joey_pref` is "down"; or the role is "other"; or the title has a hardware word (hardware, firmware,
     embedded, silicon, chip, VLSI, ASIC, FPGA, RF, mechanical, electrical); or the role is ai_engineering and the title
     says machine learning / ML / computer vision / deep learning, unless it also names a client-facing function
     (forward deployed, solutions, customer, field, consultant, consulting, implementation).
   - "top" if `joey_pref` is "up" or the role is ai_pm.
   - otherwise "standard".
   `joey_pref` "up" / "down" wins over everything above except the target gate (an off-target row stays off_target).
3. **Chance factors**, each in [0, 1]:
   - s_referral: `referral` starting "1st-degree" → 1.0; containing "LinkedIn" → 0.8; starting "Warm" → 0.6;
     "School alumni" → 0.4; anything else / missing → 0.0.
   - s_timing: title or `sources` contains "summer 2027" / "2027 summer" (any case) → 1.0; else contains "summer" or
     "2027" → 0.8; else 0.5.
   - s_sponsor: `sponsorship` "Posting offers sponsorship" → 1.0; "Strong H-1B sponsor" → 0.8; "Some H-1B history" → 0.6;
     anything else → 0.4 (a "Blocked…" value → 0.0, except "Blocked: no sponsorship" → 0.2, JSA-385).
   - s_fresh: age = days from `posted` to `added` (both YYYY-MM-DD; a date is used up to its first 10 characters):
     ≤ 7 → 1.0; ≤ 14 → 0.8; ≤ 30 → 0.6; ≤ 90 → 0.3; older, negative age counts as 0 days, missing / unreadable date → 0.2.
     (It never uses today's date, so a row's score does not drift day by day.)
   - s_chance = 0.40·s_referral + 0.25·s_timing + 0.10·s_sponsor + 0.25·s_fresh (JSA-385: was 0.20 / 0.15), rounded to 3 decimals.
4. **Score.** s_value = 70 for top, 40 for standard, 0 for exclude and off_target. score = s_value + 30·s_chance,
   rounded to 1 decimal.
5. **Tier** follows the value level (2026-11-03: score cut-offs were arbitrary again): tier_orig = "A" for top;
   "B" for standard with s_chance ≥ 0.5; "C" for standard with s_chance < 0.5; "D" for exclude and off_target.
   tier = "Blocked" if `elig` is 不可投, 已关闭 or 重复, or `sponsorship` starts with "Blocked" other than "Blocked: no sponsorship" (JSA-385: that label no longer blocks); otherwise
   tier = tier_orig. A row whose `elig_codes` contain NO_FUTURE_SPONSORSHIP_INTERN (the posting wants a candidate who never
   needs sponsorship) gets tier_orig one lower — A→B, B→C, C/D unchanged (JSA-385).
6. Input rows are not mutated; scoring a scored row again gives the same row (idempotent).
