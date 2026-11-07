Return {"cases": [...]}. Each case:
{"name": "...", "fn": one of "detect_ats_f" | "clean_ident" | "page_systems" | "big_tech" | "throne_location" | "parse_throne" |
 "csod_session" | "parse_csod" | "parse_gem" | "parse_pageup" | "parse_personio" | "parse_recruiterbox" | "schema_location" |
 "parse_softgarden" | "join_company_id" | "parse_join" | "keka_identifier" | "parse_keka" | "parse_gupy" | "parse_hrmos" |
 "parse_herp" | "beisen_portal" | "parse_beisen",
 "args": detect_ats_f {"text": str} · clean_ident {"system": str, "ident": str} · page_systems {"url": str, "page": str} ·
   big_tech {"company": str} · throne_location {"item": obj} · parse_throne {"d": any, "tenant": "tiktok"|"usds"|"bytedance"} ·
   csod_session {"page": str} · parse_csod {"d": any, "host": str, "site": str, "slug": str} · parse_gem {"d": any, "slug": str} ·
   parse_pageup {"page": str, "base": str} · parse_personio {"d": any, "host": str} · parse_recruiterbox {"d": any} ·
   schema_location {"loc": any} · parse_softgarden {"d": any} · join_company_id {"page": str} · parse_join {"d": any, "slug": str} ·
   keka_identifier {"page": str} · parse_keka {"d": any, "host": str} · parse_gupy {"page": str, "host": str} ·
   parse_hrmos {"page": str} · parse_herp {"page": str, "slug": str} · beisen_portal {"page": str} · parse_beisen {"d": any, "host": str},
 "expect": detect_ats_f → list of [system, ident] for ONLY the systems of Addition f (tiktok, bytedance, cornerstone, gem, pageup,
   personio, recruiterbox, softgarden, join, keka, gupy, hrmos, herp, beisen, moka, darwinbox, and eightfold / avature / ultipro;
   others ignored), in order of first appearance per system order is NOT tested — give them sorted by system then ident ·
   clean_ident / join_company_id / keka_identifier / beisen_portal / throne_location / schema_location → string or null ·
   csod_session → [token, api] or [null, null] · page_systems / big_tech → list of [system, ident] · parse_* → list of
   {"title", "location", "url"} in page / list order,
 "spec_quote": "...", "ambiguous": false}
Write only cases for "Addition (2026-11-04, f)": 40 cases — detect_ats_f 8 (a mix of the new hosts in one text, the
na.api.csod.com trap, a pageup mob/ link, keka careers/jobdetails link, avature own-domain SearchJobs with en_US, eightfold
apply.careers host, an ultipro.ca board, moka + darwinbox), clean_ident 10 (tiktok ×2, cornerstone with and without site, pageup,
keka jobdetails, a vendor personio slug, gem 'api', avature custom with locale, eightfold bare company domain), page_systems 3,
big_tech 3, throne_location 1, parse_throne 1, csod_session 2, and one each for parse_csod, parse_gem, parse_pageup,
parse_personio, parse_recruiterbox, schema_location, parse_softgarden, join_company_id, parse_join, keka_identifier, parse_keka,
parse_gupy, parse_hrmos, parse_herp, beisen_portal. Keep snippets short and realistic.
