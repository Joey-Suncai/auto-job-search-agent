Return a JSON array of 8 cases, same shape as before: {"name","why","facts","master","expect_kinds"}. Focus on star_missing:
facts with empty / whitespace-only S, T, A or R; a bullet citing two facts that together cover all four (no problem); a reserve bullet with a
gap; a bullet citing an unknown id (then star_missing is not judged — only unknown_fact and the number rule apply). Every fact in other bullets
must have S, T, A, R non-empty. Keep everything else clean (STAR bullet text as described, numbers from cited facts, all resume entries present).
Master bullets must mix sentence shapes (no shape on more than ceil(40 %) of the bullets of a case) and follow the why / problem rule. Bold lists may be empty.
