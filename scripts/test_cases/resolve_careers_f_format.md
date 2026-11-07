Return {"cases": [...]}. Each case:
{"name": "...", "fn": "names_company" | "is_challenge" | "detect_ats" | "career_links" | "wikidata_pick" | "alias_domains" | "looks_like_title" | "paren_acronym" | "foreign_host",
 "args": names_company {"page": str (HTML), "company": str, "final_url": str or ""} · is_challenge {"status": int, "page": str} ·
   detect_ats {"text": str} · career_links {"page": str (HTML), "base": str} · wikidata_pick {"company": str, "results": list} ·
   alias_domains {"company": str, "table": object} · looks_like_title {"company": str} · paren_acronym {"company": str} · foreign_host {"host": str},
 "expect": names_company / is_challenge / looks_like_title / foreign_host → bool · detect_ats → list of [system, ident] (ident a string) ·
   career_links → list of URL strings · wikidata_pick → list of ids · alias_domains → list of strings · paren_acronym → string,
 "spec_quote": "...", "ambiguous": false}
Write only cases for "Addition (2026-11-03, f)": 30 cases — names_company 9 (copyright / og / JSON-LD evidence, strong host
with a slogan title, a first-word-only host that is NOT strong, country-code host, ww38 parking, for-sale page, domain-token
title, initials before suffix removal), is_challenge 3, detect_ats 2, career_links 3 (ordering), wikidata_pick 4, alias_domains 3,
looks_like_title 3, paren_acronym 2, foreign_host 1. Keep HTML short.
