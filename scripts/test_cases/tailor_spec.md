# tailor — JD terms and mechanical tailoring (for writing test cases; you do not see the code)

Role library: {"competencies": [{"id","weight","keywords": [{"term","synonyms": [...]}]}]}. A spelling matches a text when it appears as a
whole token, case-insensitive (letters/digits around it break the match: "LLM" does not match "LLMOps"; "AI tools" matches "ai tools").

## 1. jd_terms(jd, role, title, n=12) → list
For every keyword (cluster = term + synonyms): count = for each spelling, how many times it matches in the jd; hits = their sum. Clusters
with hits 0 are skipped. in_title = any spelling matches the title. score = competency weight × min(hits, 3) × (2 if in_title else 1),
rounded to 4 decimals. jd_spelling = the spelling with the most matches (ties → the longer spelling). Sort by score descending, then hits
descending, then term alphabetically; keep the first n.

## 2. parse_jd(text, folder) → (title, company)
Take the first line starting with "# ". Split the rest on " — " (an em dash with spaces; an en dash "–" or hyphen does NOT split). With one
part: (that part, ""). Otherwise: key = the folder's last path part, lower-cased, with a leading "YYYY-MM-DD_" removed. The company is the
first part p for which key starts with the first 12 characters of slug(p) (slug = lower-case, every run of non-letters/digits → "_",
leading/trailing "_" stripped); if none (or no folder), the last part. Title = the remaining parts joined with " — ". No "# " line → ("", "").

## 3. tailor(master, facts, role, jd, title) → tailored master + changes
truth of a cluster: "true" when a fact with resume_ok not false, whose entry has on_resume not false, has a skill matching a spelling
(whole token, or equal ignoring case), or a skills.true item does; else "not used" when a spelling is in skills.not_true (ignoring case);
else "not true". page text = headline + summary + skills items + bullet texts.
- swap: for a true term whose jd_spelling is not on the page but another spelling s of the cluster is, and s / jd_spelling pass
  is_bullet_variant (same words up to case / hyphens, or acronym ↔ expansion, with the same grammatical number — "workflow"/"workflows"
  is NOT allowed): every bullet holding s gets s replaced by jd_spelling; a skills item equal to s is replaced when jd_spelling is a true
  skill. The swap is recorded only when a bullet or skills item changed (a spelling only in the headline or summary is left as approved).
- skill added: a true term whose jd_spelling is still not on the page and is itself a true skill (skills.true or a resume_ok fact's
  skills, ignoring case) is appended to one skills group (the group holding most skills of the term's evidence facts).
- alternates: for each reserve bullet in order whose entry is on the master with ≥ 2 bullets: what it "brings" = the JD terms it holds
  in any spelling that the page does not hold in any spelling, plus the terms it holds in the jd_spelling while the page holds them only
  in another spelling (a term already brought as new is not counted twice). Nothing brought → skip. Otherwise it replaces one non-core
  bullet of its entry (core = the entry's first bullet, or any bullet with "core": true; a core bullet is never replaced) whose removal
  loses nothing: every term the removed bullet holds (any spelling) and every term it holds in the
  jd_spelling must still be on the rest of the page in the same way. Among those, the bullet with the lowest top competency weight
  (its "competencies" list; none = 0) goes, ties → the later bullet. The removed bullet takes the reserve slot.
- order: an entry's core bullets come first, in their master order; the others follow, sorted by how many JD terms they hold (more
  first, stable). A reserve bullet that came in carries no "core" mark unless its own record has one.
- headline (when a title is given): title, then up to 3 jd_spellings of true terms that are true skills and are not inside the title
  (case-insensitive), in jd_terms order, joined with " · ".
Never: a new sentence, a changed summary, a term that is not true.
