Return a JSON array of 26 cases:
{"name": "snake_case_unique",
 "field": {"label": "the question text as the form shows it", "description": "optional extra text or empty", "options": ["…"] or []},
 "citizen": true | false,
 "expect": {"kind": "export_control" | "export_control_maybe" | "citizenship" | "clearance" | null, "blocks": true | false}}
citizen = the candidate is a U.S. citizen or permanent resident. Mostly citizen false; include 4 citizen true cases.
Split: 7 export_control (some with the identity words only in the options), 4 export_control_maybe, 5 citizenship,
3 clearance, 7 none (near misses: status questions without a requirement, sponsorship questions, export words with no
identity status).
