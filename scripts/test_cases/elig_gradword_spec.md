# Spec: graduation-window rule vs. the word "graduate" (JSA-087)

classify(job) → "Eligible" | "Review" | "Ineligible". The candidate (default) is a master's student who graduates in
December 2027 and needs a Summer 2027 internship; the company sponsors visas.
1. A graduation window in the JD ("graduating between December 2026 and June 2027", "class of 2028", "expected graduation
   date of May 2028", "expected May 2028 graduation", "anticipated Spring 2027 graduation") → Eligible only when December 2027
   falls inside it; otherwise Ineligible. "or later" / "or after" opens the end; a single month means that month.
2. The word "graduate" used as a degree level — "graduate students", "graduate degree", "graduate program", "graduate school",
   "undergraduate or graduate students" — is NOT a graduation window, even when a date such as "Summer 2027" (the internship
   term) follows in the same sentence or the next one → no effect.
