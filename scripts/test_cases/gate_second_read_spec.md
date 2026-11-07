# Eligibility gate phase 2: rules + DeepSeek second read (JSA-231, Joey 2026-11-06)

The gate's rules give every job a result: verdict v = "Eligible" | "Review" | "Ineligible" | "Closed" | "Unverified" and a
list of reason codes c (comma-separated). Block codes: NO_SPONSORSHIP, CITIZEN_OR_CLEARANCE, NON_US, OFF_CYCLE, TOO_LONG,
UNDERGRAD_ONLY, PHD_ONLY, EXPERIENCE_3PLUS, MBA_ONLY, GRAD_WINDOW, CLOSED. Soft block codes: OFF_CYCLE, UNDERGRAD_ONLY,
NO_SPONSORSHIP, GRAD_WINDOW. Review codes include SPONSORSHIP_MIXED, GRAD_MIXED, BACHELORS_WORDING, EXPERIENCE_2,
PART_TIME_IN_TERM. Plus codes (GRAD_OK, OFFERS_SPONSORSHIP) are neither. Codes meaning the JD was not read: UNREADABLE,
NO_TEXT, FETCH_ERROR, POSSIBLY_EXPIRED, CLOSED.

1. Which results DeepSeek re-reads:
   - "soft_block": v is Ineligible and EVERY block code in c is a soft block code (plus/review codes may also be present).
     One hard block code (e.g. NO_SPONSORSHIP + CITIZEN_OR_CLEARANCE) → no re-read: the rules decide.
   - "review": v is Review.
   - Nothing else (Eligible, Closed, Unverified, hard Ineligible). Any not-read code in c → no re-read.
2. DeepSeek answers eligible = "yes" | "no" | "unclear" (or fails: no answer, or an answer with another value).
3. Outcome:
   - soft_block + "no" → stays Ineligible, codes unchanged.
   - soft_block + "yes" or "unclear" → v becomes Review and the code DS_SECOND_READ is appended to c (the original codes
     stay). Never Eligible.
   - review + any answer → v stays Review, codes unchanged (never Eligible, never Ineligible).
   - Whenever a valid answer exists for a re-read result, the answer is attached (field ds) for the human check.
   - No valid answer → the result is returned exactly as the rules gave it (no ds attached).
4. Results that are not re-read are returned unchanged, with no ds.
