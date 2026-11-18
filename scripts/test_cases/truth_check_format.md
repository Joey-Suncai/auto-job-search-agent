Return a JSON array of cases. Three kinds of case, by "fn":
- {"name","why","fn": "variant","a","b","expect_variant": bool,"expect_bullet_variant": bool}
- {"name","why","fn": "text","text","jd","profile","facts": {...},"expect_kinds": [...]}  (kinds: number, never, pair, banned; a set, empty = clean)
- {"name","why","fn": "tailored","facts": {...},"approved": {...},"tailored": {...},"title": "...","expect_kinds": [...]}
  (kinds: swap_not_variant, new_sentence, entry_moved, fact_ids_changed, summary_changed, headline_term, skill_added_untrue; a set)
About 10 variant cases (plural, hyphen, case, acronym ↔ expansion singular/plural, near misses), 10 text cases (team-of-3 overclaims via a
never phrase such as "independently" vs the allowed "led the code" (Joey 2026-11-09: "led most of the code" is now the never phrase), a 70% claim without its pair word, numbers from the jd / profile /
entry dates that are fine, phone numbers and URLs, a banned word that is the company's name), 10 tailored cases (a clean reorder, a clean
swap LLM → large language model, a plural swap, an invented sentence, a bullet moved, fact ids changed, summary edited, an untrue headline
term, a Summer 2027 headline part, an untrue skill added). Small fictional fact bases. In tailored cases keep both masters' bullets valid
(real action-verb sentences) — only the listed kinds are compared.
