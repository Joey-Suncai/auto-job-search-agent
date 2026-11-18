# gap_reserve — wording gaps → reserve bullets (for writing test cases; you do not see the code)

A spelling matches a text when it appears as a whole token, case-insensitive (letters / digits / "&" / "+" next to it break the match:
"LLM" does not match "LLMOps"; "API" does not match "APIs"). A skill string s "matches a cluster" (term + synonyms) when any spelling
matches inside s as a whole token, or s equals a spelling ignoring case and surrounding spaces ("stakeholder needs" matches the cluster
["stakeholders","stakeholder"] because "stakeholder" is a token of it).

Fact base: {"entries": [{"id","org","role","on_resume"}], "facts": [{"id","entry","skills","resume_ok"}], "skills": {"true": {group: [..]},
"not_true": [..]}}. Role library: {"competencies": [{"id","weight","keywords": [{"term","synonyms"}]}]}.

## 1. tags_for(spellings, facts) → [[fact_id, skill], ...]
Every skill of a fact with resume_ok not false, whose entry has on_resume not false, that matches the cluster, in fact order then skill
order; then every skills.true item (groups in their order) that matches, as ["skills.true", item].

## 2. jd_gaps(jd, title, role, facts, page, n=12) → list
Take jd_terms(jd, role, title, n): for every cluster, hits = total matches of all its spellings in the jd (clusters with 0 hits skipped);
in_title = any spelling matches the title; score = weight × min(hits, 3) × (2 if in_title else 1), rounded to 4 decimals; jd_spelling =
the spelling with the most matches (tie → the longer one); sorted by score desc, hits desc, term asc; first n.
Keep a term only when (a) it is "true": a fact as in §1 has a matching skill, or a skills.true item matches, and (b) the page does not
contain its jd_spelling. state = "other_spelling" when another spelling of the cluster is on the page, else "missing".
Each kept item: {term, jd_spelling, state, score, facts: [ids of facts with a matching skill, fact order]}.

## 3. aggregate(per_jd, n_jds) → rows
per_jd = a list (one per JD) of jd_gaps lists. One row per term: jds = in how many lists it appears; share = jds / n_jds rounded to 4
decimals (0 when n_jds is 0); score = sum of its scores rounded to 4; spellings = {jd_spelling: count}; states = {state: count}; facts =
the sorted union of facts. Rows sorted by score desc, then jds desc, then term asc.

## 4. deny(facts, spellings, fact_id) → removed skills (and the facts are changed in place)
fact_id = a fact id: that fact's skills that match the cluster are removed (others kept, order kept); returns the removed ones in order.
fact_id = "skills.true": the same for every skills.true group. An unknown id or nothing matching → [] and nothing changes. Other facts
are never touched.

## 5. check_candidates own rules (master, candidates) → problems
master = {"entries": [{"entry_id","bullets": [{"text"}]}], "reserve": [{"text"}]}. candidate = {entry_id, text, fact_ids, bold, gap}.
Each candidate i (1-based) gives, in this order:
- entry_not_on_master — its entry_id is not an entry_id of the master;
- not_new — its text equals an existing master bullet or reserve text exactly;
- no_gap_term — gap is empty, or no spelling of gap's cluster (the role keyword whose term or a synonym equals gap ignoring case; if
  none, just gap itself) matches the text.
(The full checker also runs the resume truth rules; these cases only test the three above.)

## 6. bank_insert(bank_text, heading, lines) → text
Find the line "## <heading>" (exact after strip). Insert the lines at the end of that section — right after its last non-empty line
before the next line starting with "## " (or the end) — keeping the blank line(s) that follow. No such heading → append "\n\n## heading\n"
+ the lines at the end. The result always ends with exactly one "\n" (trailing newlines of the input are stripped first).
