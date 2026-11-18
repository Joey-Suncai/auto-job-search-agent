# direction_master.check — truth checks on a written master resume (for writing test cases; you do not see the code)

Inputs: a fact base {"entries": [{"id","kind","org","role","dates","on_resume": bool,"never": [...]}], "facts": [{"id","entry","S","T","A","R",
"numbers": [...],"skills": [...],"never": [...],"pairs": [[a,b]],"resume_ok": bool,"history": [...]}], "skills": {"true": {"Group": [...]},
"not_true": [...]}} and a master {"headline","summary","skills": [{"label","items": [...]}],"entries": [{"entry_id","bullets": [{"text","fact_ids","competencies"}]}],
"reserve": [{"entry_id","text","fact_ids"}],"notes"}.
Resume entries = entries with on_resume true, kind not "education", and at least one fact whose resume_ok is not false and whose
"bullet_ok" is not false (a fact may carry "bullet_ok": false = true, but never written as a resume bullet). Problems (each a kind):
- not_resume_entry: a master entry_id that is not a resume entry.
- entries_missing: a resume entry with no master entry.
- too_many: more bullets than the entry's maximum (jsa 5, hp 3, stock 2, fs 2, voice 3; any other id 5).
- no_fact_ids: a bullet (or reserve bullet) with an empty fact_ids list.
- unknown_fact / wrong_entry / off_resume / not_bullet: a cited id that does not exist / belongs to another entry / has resume_ok false /
  has bullet_ok false.
- number: a number in the bullet text that is not among the CURRENT numbers of the cited facts (their S/T/A/R text and "numbers"; a fact's
  "history" does NOT count). Normalization: ¥ $ € £ % + and thousands commas removed, decimals kept; "0–5" and "2017–2018" are two numbers each;
  digits inside words count too ("F-1" contains the number 1).
- never: the bullet contains (case-insensitive, whole phrase) a "never" phrase of its entry or of a cited fact.
- pair: a cited fact has pair [a, b], the bullet contains a (case-insensitive substring) but not b.
- star_missing: a bullet (or reserve bullet) whose cited facts (all of them existing) together have an empty S, T, A or R — every STAR part
  must come from at least one cited fact (non-empty after trimming). Checked per bullet over the union of its cited facts.
- skill_not_true: a skills item equal (ignoring case) to an entry of skills.not_true.
- skill_unknown: a skills item that is neither in skills.true (any group except one named "Languages" — spoken languages stay off resumes) nor in the skills of any fact with resume_ok not false (ignoring case).
- summary_number: a number in the summary that is not a current number of any resume_ok fact.
- summary_never: the summary contains any never phrase of any entry or fact.
- summary_length: summary longer than 320 characters.
Bold terms: each bullet (and reserve bullet) may carry "bold": [terms]:
- bold_too_many: more than 2 terms;
- bold_missing: a term that is empty or not written exactly (case-sensitive substring) in the bullet text;
- bold_unknown: a term that contains a digit, or that (ignoring case) is neither a skill of a cited fact, nor in skills.true (any group except
  "Languages"), nor in the skills of any resume_ok fact. (In these tests there is no role library.)
The bullet rules of check_bullets also apply to master bullets (kinds: opener, verb, why, problem, length, banned, repeated_verb,
shape_dominant, few_shapes, outcome_first, causal): with a number a bullet needs a reason (" to ", "so ", " for ", "when " …); without a number it needs a problem word ("when", "found", "mismatch",
"slow" …); its FIRST word is an action verb — a bullet opening with a context phrase ("To …, ", "When …, ", "Because …, ": 2–16 words
before the first comma, first word to/when/with/after/because/as/for/asked/using/…) is an "opener" problem; a "causal" problem: the text contains (case-insensitive, whole word) "because", "since" (unless the next word starts with a digit, e.g. "since 2024"), "due to" or "owing to" (Joey 2026-11-09: no because-style clauses); in an entry with 2+ bullets,
if a later bullet has a digit the first must have one too ("outcome_first"); no sentence shape on more than ceil(40 %) of the bullets. Keep master bullets clean of
these unless a case tests them: e.g. "Built 3 dashboards to speed up reporting." (verb_purpose), "Cut costs by 5% for 3 stores; ran 2 audits." (verb_semicolon),
"Automated 4 slow reports for the sales team, saving 2 hours a week." (verb_participle) — each quantified example carries a why marker (" to ", " for ", "so " …); a number with only a result and no such marker is a "why" problem — mix shapes; never open with a context phrase.
