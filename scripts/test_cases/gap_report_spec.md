# gap_report — specification of assess() and missing_tools() (for writing test cases; you do not see the code)

Inputs
- role: {"competencies": [{"id", "label", "weight", "df", "keywords": [{"term", "synonyms": [...], "df"}]}]} (already sorted by weight, highest first).
- facts base: {"facts": [{"id", "A", "R", "skills": [...], "resume_ok": true|false (missing = true)}], "skills": {"true": {"Group": ["skill", ...]}, "not_true": ["tool", ...]}}.

Matching: a keyword group = its term plus synonyms ("spellings"). A string matches the group when any spelling occurs in it as a whole token, case-insensitive
(the character before must not be a letter, digit, "_", "&", "+" or "/"; after must not be a letter, digit, "_", "&" or "+"), or when the string equals a spelling ignoring case.

assess(role, facts, min_weight=0.03, proven_share=0.5) returns one row per competency whose weight ≥ min_weight, in the role's order:
1. Skill match: facts with resume_ok not false whose "skills" list has a string matching a keyword group. covered = those groups' terms.
   coverage = (sum of df of covered groups) / (sum of df of all groups of the competency). If the sum of all df is 0: coverage = 1.0 when something is covered.
   coverage ≥ proven_share → level "proven"; coverage > 0 but < proven_share → "partial". (If groups are covered but all their df are 0 while others have df > 0, coverage is 0 → "partial".)
2. Otherwise, if a resume_ok fact's A or R text matches a group (whole-token rule) → "mentioned" (coverage 0).
3. Otherwise, if any skill in skills.true (all groups flattened) matches a group → "listed only".
4. Otherwise, if a resume_ok = false fact matches by skills or by A/R text → "off resume".
5. Otherwise "gap".
Row fields: id, level, coverage (rounded to 3 decimals; 0.0 unless proven/partial), facts (ids of the facts found at the level that decided, unique, in fact order),
keywords (matched terms, unique), missing (terms of groups with df > 0 that are not covered, most-asked first by df, at most 5; for levels other than proven/partial every group with df > 0 counts as not covered).

missing_tools(role, facts) → list of (tool, df) for each skills.not_true entry that equals (ignoring case) a spelling of some keyword group in the role; df = that group's df
(the largest if several). Sorted by df descending, then tool name ascending. Tools not in the role are left out.
