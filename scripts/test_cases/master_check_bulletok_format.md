Return a JSON array of 8 cases, same shape as before: {"name","why","facts","master","expect_kinds"}. Focus on the bullet_ok rules:
a cited fact with bullet_ok false (not_bullet); an entry whose only facts are bullet_ok false (it is NOT a resume entry: a master entry for it
is not_resume_entry, leaving it out is fine); an entry with on_resume false; bullet_ok missing (= allowed). Every fact a bullet cites must have
non-empty S, T, A, R unless the case tests star_missing. Keep everything else clean (STAR bullet text, numbers from cited facts, all resume entries present).
Master bullets must mix sentence shapes (no shape on more than ceil(40 %) of the bullets of a case) and follow the why / problem rule. Bold lists may be empty.
