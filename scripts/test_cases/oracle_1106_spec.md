# Oracle runner helpers, second round (JSA-226, 2026-11-05)

1. `degree_option(want, options)` — the education card's Degree list option for a wanted degree word ("Master's",
   "Bachelor's", "Doctorate"). Comparison ignores case, surrounding/multiple spaces and curly vs straight apostrophes
   (’ = '). Order: an option equal to `want`; else the first option that starts with `want` ("Master's Degree");
   else the first option that contains `want` as a whole word, but never an option with the word "post" in it
   ("Post doctorate degree" is not Doctorate). None when nothing fits or `want` is empty.
2. `tenant_id(url)` — the Oracle pod id of a posting URL: only hosts containing "oraclecloud.com" count (else "");
   take the first host label, drop a leading "fa-", then keep what is before the next "-". Lower case.
   "https://egud.fa.us2.oraclecloud.com/hcmUI/…" → "egud"; "https://fa-ewgu-saasfaprod1.fa.ocs.oraclecloud.com/…" → "ewgu".
3. `code_mail_ok(sender, body, tenant, company)` — whether a one-time-code e-mail belongs to this tenant's application.
   If the sender (the From header) contains "<pod>.fa.sender" (Oracle's own sender), it is OK only when <pod> equals
   `tenant` (case-insensitive; an empty tenant → not OK). Otherwise (a company's own sender) it is OK when the first word
   of `company` appears (case-insensitive) in the sender or the body; when no company is given it is OK.
4. `box_fit(label, kind, value, box)` — does a text answer fit the box? Only kinds "text" / "textarea" are judged and a
   None value always fits (None). `box` = {"maxlength", "type", "inputmode", "block"}. An amount box is: type "number",
   or inputmode "numeric"/"decimal", or block "work-preferences" with a label naming salary / pay / compensation / wage /
   rate but not currency / frequency / period / type / unit / basis. In an amount box, a value that is not a plain
   amount ("85000", "$85,000", "25.50") → "not_number". Else, a value longer than an integer maxlength > 0 →
   "too_long". Else None.
5. `edu_fill(school, education, today)` fallback — when no education entry's match_re / school name is found in the
   card text, the card may name only a degree and an end month ("B.A. in Economics From No date provided to May 2026"):
   the entry whose level matches the card's degree word (B.A./B.S./Bachelor → "bachelor", M.S./M.A./Master → "master",
   Ph.D./Doctor → "phd") AND whose `end` ("YYYY-MM") equals a month written on the card ("May 2026" → "2026-05") is used,
   only when exactly one entry matches; the result then also carries "school" (the entry's school). The card's letters
   may also be split by spaces ("U NIVERSITY OF C HICAGO"): a match_re found in the text with spaces removed counts.
   No match → None.
