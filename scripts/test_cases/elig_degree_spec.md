# Spec: the eligibility gate's degree-level rules depend on the candidate (JSA-087)

classify(job) returns "Eligible" | "Review" | "Ineligible". setCandidate({degree_level}) sets the degree the candidate is
currently enrolled in: "bachelors", "masters" (default) or "phd". These rules apply to INTERNSHIPS only (title says intern /
internship); full-time roles are not affected by degree level.

For a "masters" or "phd" candidate (graduate student):
1. A JD limited to class years — "juniors only", "open to juniors", "rising junior/senior/sophomore", "juniors or seniors",
   "freshman", "undergraduate students only", "bachelor's students only" → Ineligible, unless the JD also accepts graduate
   students (master's, graduate student/degree, MS, PhD, "graduate or undergraduate", "all education levels"); an explicit
   "juniors only" / "open to juniors" stays Ineligible even then.
2. A JD that asks for someone "currently pursuing / enrolled in a bachelor's / undergraduate degree" (and does not also accept
   graduate students) → Review.
3. "Currently pursuing a PhD" with no mention of master's / bachelor's → Ineligible for a "masters" candidate; no effect for a
   "phd" candidate.
For a "bachelors" candidate (currently enrolled undergraduate):
4. "Currently pursuing / enrolled in a bachelor's / undergraduate degree" → no effect (Eligible if nothing else applies).
5. A class-year limit (juniors only, rising senior, juniors or seniors, freshman …) → Review (the candidate's year is unknown).
6. A JD that requires current enrolment in a master's / graduate / PhD program and never mentions bachelor's / undergraduate
   students → Review.
7. "Currently pursuing a PhD" with no mention of master's / bachelor's → Ineligible.
Everything else (sponsorship, location, dates, MBA-only) is unchanged; keep it neutral in the cases.
