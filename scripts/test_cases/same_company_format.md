Return a JSON array of test cases. Each case:
{"name": "short unique snake_case name",
 "ids": ["J1", ...],
 "apps": [{"job_id": "J1", "company": "Acme", "title": "Data Intern", "applied_on": "2026-10-31"}, ...],
 "emails": [{"job_id": "J1", "type": "Confirmation"}, ...],
 "kind": "Confirmation",
 "expect": "J1"}            // the job_id of the returned row, or null for None
