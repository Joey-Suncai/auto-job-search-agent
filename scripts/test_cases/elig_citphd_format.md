Return a JSON array of 24 cases:
{"name": "snake_case_unique", "candidate": {"degree_level": "masters" | "phd", "citizen": true | false},
 "title": "AI Research Intern, Summer 2027", "loc": "Boston, MA", "level": "Internship",
 "text": "a realistic job description of AT LEAST 300 characters with the sentence under test; it states that the company sponsors visas (except where the citizen-only sentence makes that moot)",
 "expect": "Eligible" | "Review" | "Ineligible"}
Split: 11 citizenship cases (non-citizen vs citizen pairs, near misses that must stay Eligible), 13 PhD cases (requirement
sentence, after "Qualifications:", "welcome/encouraged" invitations, master's also named, a phd candidate, old "pursuing a PhD").
