Return a JSON array of 5 cases, same shape as before: {"name","why","facts","master","expect_kinds"}. Focus only on the skills rules:
a skills.true group named "Languages" (its items must be reported as skill_unknown when listed in the master's skills), the same word
appearing in another skills.true group or in a resume_ok fact's skills (then it is fine), and not_true items. Keep everything else in the
master clean (STAR bullets as described, numbers from the cited facts, every resume entry present).
Every fact that a bullet cites must have non-empty S, T, A and R (the star_missing rule) unless the case tests star_missing.
Master bullets must mix sentence shapes (no shape on more than ceil(40 %) of the bullets of a case) and follow the why / problem rule. Bold lists may be empty.
