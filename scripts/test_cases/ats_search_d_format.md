Return {"cases": [...]}. Each case:
{"name": "...", "fn": one of "detect_ats" | "clean_ident" | "parse_adp" | "paycom_config" | "parse_paylocity" | "parse_dayforce" |
 "brassring_session" | "parse_brassring" | "clearcompany_site_id" | "parse_clearcompany",
 "args": detect_ats {"text": str} · clean_ident {"system": str, "ident": str} · parse_adp {"d": object, "host": str, "cid": str, "ccid": str} ·
   paycom_config {"page": str} · parse_paylocity {"page": str} · parse_dayforce {"d": any, "tenant": str, "board": str} ·
   brassring_session {"page": str} · parse_brassring {"d": object} · clearcompany_site_id {"page": str} · parse_clearcompany {"d": object},
 "expect": detect_ats → list of [system, ident] for ONLY the six systems of Addition d (other systems in the text are ignored by the
   harness) · clean_ident → string or null · parse_* → list of {"title", "location", "url"} · paycom_config / brassring_session →
   [str, str] or null · clearcompany_site_id → string or null,
 "spec_quote": "...", "ambiguous": false}
Write only cases for "Addition (2026-11-03, d)": 30 cases — detect_ats 6 (one per system), clean_ident 9 (adp with &amp; and
with a missing ccId, brassring with &#038;, paycom, paylocity, dayforce with and without a locale and the locale-only URL,
clearcompany bare host), parse_adp 2, paycom_config 3 (good, foreign service host, missing libConfig), parse_paylocity 2
(one internal job skipped), parse_dayforce 2, brassring_session 2, parse_brassring 2, clearcompany_site_id 1, parse_clearcompany 1.
Keep snippets short and realistic.
