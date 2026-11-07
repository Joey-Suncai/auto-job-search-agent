# Spec: the eligibility gate depends on the candidate (JSA-081)

classify(job) returns a verdict: "Eligible" | "Review" | "Ineligible". setCandidate({needs_sponsorship, citizen_or_pr, grad})
sets who is applying (grad = expected graduation as "YYYY-MM"). Default: needs_sponsorship true, citizen_or_pr false, grad "2027-12".
Only these three behaviours depend on the candidate:
1. The job says it will NOT sponsor visas ("unable to sponsor", "no visa sponsorship", "must not require sponsorship now or in
   the future"): Ineligible when needs_sponsorship is true (unless the same text also says it can sponsor → Review);
   no effect at all when needs_sponsorship is false.
2. The job requires U.S. citizenship / permanent residency / a security clearance / export-control U.S.-person status:
   Ineligible when citizen_or_pr is false; Review (not Ineligible) when citizen_or_pr is true.
3. The job states a graduation window ("graduating between December 2026 and June 2027", "class of 2027 or later"): Eligible
   only when the candidate's grad date falls inside it; outside → Ineligible.
A job with none of these, a U.S. location, a readable description (≥ 200 characters) and nothing else disqualifying is Eligible.
