Return {"cases": [...]}. Each case:
{"name": "...", "fn": one of "backoff" | "is_blocked" | "parse_icims" | "parse_sitemal" | "parse_oracle" | "parse_jazz" |
 "jobvite_range" | "parse_rss" | "parse_avature" | "ukg_load_url" | "clean_ident",
 "args": backoff {"attempt": int, "retry_after": str or null} · is_blocked {"status": int, "body": str} ·
   parse_icims {"page": str, "host": str} · parse_sitemal {"xml": str} · parse_oracle {"d": object, "host": str, "site": str} ·
   parse_jazz {"page": str, "host": str} · jobvite_range {"page": str} · parse_rss {"xml": str} · parse_avature {"page": str} ·
   ukg_load_url {"page": str, "host": str, "tenant": str} · clean_ident {"system": str, "ident": str},
 "expect": backoff → number · is_blocked → bool · parse_* → list of {"title", "location", "url"} · jobvite_range → [s, e, t] or null ·
   ukg_load_url → string or null · clean_ident → string or null,
 "spec_quote": "...", "ambiguous": false}
Write only cases for "Addition (2026-11-03, c)": 28 cases — backoff 4, is_blocked 5 (incl. the PCSX 403 JSON and a 500),
parse_icims 2, parse_sitemal 3, parse_oracle 1, parse_jazz 2, jobvite_range 2, parse_rss 2, parse_avature 2, ukg_load_url 3,
clean_ident 2. Keep snippets short and realistic.
