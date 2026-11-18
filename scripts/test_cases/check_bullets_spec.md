# check_bullets — bullet rules (for writing test cases; you do not see the code)

Rules (the candidate's, 2026-11-08): a bullet WITH a number = what was done + why + impact; a bullet WITHOUT a number = the problem + how it
was solved; sentence shapes vary across the page; every bullet opens with its action verb (2026-11-09: never with a context phrase).

Context phrase: the words before the FIRST comma or colon, when they are 2–16 words and the first word (case-insensitive, a leading quote
ignored) is one of: to, when, with, after, facing, because, as, for, given, asked, before, while, seeing, needing, starting, building,
running, using, across, from, without.

check_bullet(text) → list of problems. Kinds:
0. opener: the text opens with a context phrase (defined above). When this fires, rule 1 (verb) is NOT checked for that bullet.
1. verb: (only when no opener problem) the first word of the text must be an action verb.
   Action verb = in this list (case-insensitive): led, built, ran, set, cut, won, made, wrote, drove, grew, took, found, chose, held,
   designed, operate, operates, run, runs, own, owns, turned, compared, benchmarked, engineered, specified, organized, produced, created,
   co-built, defined, shipped, launched, analyzed, tested, evaluated, audited, measured, automated, replaced, scoped, prioritized, presented,
   translated, taught, gave, kept, brought, sold, oversaw, began, got, put, met, spoke, rebuilt, rewrote — OR a word ending in "ed", longer
   than 3 letters, not one of: red, bed, need, seed, feed, speed, based, related, advanced, detailed.
2. why (only when the text contains a digit): there must be one of these substrings in " " + lower(text) + " ":
   " to ", "so that", "so ", "enabling", "allowing", "to meet", " for ", "when ", "after ".
3. problem (only when the text contains NO digit): there must be one of these substrings in lower(text): "when",
   "found", "mismatch", "disagree", "inconsistent", "scattered", "slow", "wrong", "invent", "without", "gap", "error",
   "duplicate", "unclear", "manual".
3b. causal: a "causal" problem: the text contains (case-insensitive, whole word) "because", "since" (unless the next word starts with a digit, e.g. "since 2024"), "due to" or "owing to" (Joey 2026-11-09: no because-style clauses).
4. length: more than 230 characters.
5. banned: whole words leverage, leveraged, leveraging, spearhead, spearheaded, orchestrate, orchestrated, synergy, synergies, dynamic,
   passionate, results-driven, cutting-edge, go-getter, detail-oriented, team player, utilize, utilized, seamlessly, robust.

shape(text) — first that applies: "context_first" (opens with a context phrase; such a bullet also has an opener problem) · "verb_semicolon" (contains ";") · "verb_participle"
(contains ", " followed by a word ending in "ing") · "verb_purpose" (after the first word, the word "to" followed by a word) · "verb_plain".

check_master({"entries": [{"name", "bullets": [{"text"}]}]}) → every bullet problem, plus:
- too_many_bullets: an entry with more than 5 bullets;
- outcome_first: an entry with 2+ bullets whose first bullet has no digit while a later bullet of that entry has one;
- repeated_verb: an action verb (lower-cased, found as in rule 1) opening more than 2 bullets on the page;
- shape_dominant: a shape used by more than ceil(0.4 × number of bullets) bullets;
- few_shapes: 6 or more bullets but fewer than 3 different shapes.
