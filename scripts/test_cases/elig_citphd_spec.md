# Eligibility: "only U.S. citizens" and PhD-student requirements (JSA-142, 2026-11-04)

The gate classifies a job description as Eligible / Review / Ineligible for a candidate. Candidate in these cases: an
F-1 M.S. student (not a citizen or permanent resident, needs sponsorship, degree_level "masters") unless the case says
"citizen": true (then a U.S. citizen M.S. student who needs no sponsorship).

1. Citizenship only. A description that says "only U.S. citizens" (e.g. "only U.S. citizens will be considered",
   "open to only United States citizens") or "U.S. citizens only" restricts the job to citizens:
   - non-citizen candidate → Ineligible;
   - citizen candidate → this sentence alone does not block (Eligible if nothing else matters).
   Not a restriction: sentences that do not say "only U.S. citizens" / "U.S. citizens only" (e.g. "U.S. citizens and
   visa holders are welcome", "not only U.S. citizens but also international students").
2. PhD students only. For a master's candidate, a requirement sentence that starts with (or follows "Qualifications:")
   "Ph.D. students" / "PhD students" / "PhD candidates" / "Doctoral students" (e.g. "Required Qualifications: Ph.D.
   students in Computer Science or a related field.") makes the job Ineligible — unless the description also names
   master's or bachelor's students anywhere (then it is not PhD-only), or the sentence says PhD students "are welcome"
   / "are encouraged" (an invitation, not a requirement). The old wording "currently pursuing a PhD" keeps working the same way.
   A PhD candidate (degree_level "phd") is never blocked by this.
Everything else in the cases is neutral (U.S. city, Summer 2027 internship, the company sponsors visas).
