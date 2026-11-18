# Runner fixes JSA-268 … JSA-271 (2026-11-10) — pure functions

## plan_build.numeric_answer(label, src, ans) → (answer | None, source-or-reason)   (JSA-268)
An Ashby "Number" box takes digits only. Profile digits for pay: hour = "25", year = "52000".
- src == "rules:comp" (a pay answer): when the label (case-insensitive) has a whole word "annual", "yearly", "per year",
  "a year", "annum" or "salary" → ("52000", "rules:comp (digits)"); otherwise → ("25", "rules:comp (digits)").
- any other src → (None, a reason string that starts with "number box:").

## run_wd.state_on_review(value, txt) → bool   (JSA-269)
A State answer written as the full U.S. state name (any case, extra spaces allowed, e.g. "Illinois", "new york") is
shown on Workday's Review page as its two-letter postal code inside the address line. True when txt contains a comma,
optional spaces, that code in CAPITALS, and then either spaces plus a 5-digit ZIP (optionally -4 digits) or the end of a
line. Example: "Chicago, IL 60601" → True for "Illinois". A value that is not a U.S. state name (e.g. "Ontario", "IL",
"") → False. A different code (", IN 46000" for Illinois) → False.

## run_wd.block_kind_of(section) → "languages" | "education" | "work" | None   (JSA-270)
Checked in this order, case-insensitive: contains "language" → "languages"; contains "educat", "academic" or the whole
word "school"/"schools" → "education"; contains "work", "experience" or "employment" → "work"; else None.
Examples: "Schools Attended 2" → education; "Academic Experience 1" → education; "Where have you worked? 3" → work.

## run_wd.blocks_of(fields, kind) → int   (JSA-270)
fields = [{"section": str}]. The number of DISTINCT sections that end in a number (optional trailing spaces) and whose
block_kind_of is `kind`. Sections without a trailing number are not blocks.

## batch_apply.ready(status, reasons) → bool   (JSA-271)
False unless status == "dry-run". Then True when every reason is "dry-run", "batch not approved", starts with "batch not
approved", or matches "<digits> DeepSeek answer(s) to spot-check…" (also "answer" / "answers" without "(s)"). Any other
reason (e.g. "review page lacks: …", "problems: …") → False.
