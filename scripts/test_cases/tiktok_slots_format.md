Each case is a JSON object:
{
 "name": "short id",
 "job": {"company": "...", "title": "...", "level": "Internship | New grad | Full-time | ...", "url": "..."},
 "apps": [ {"job_id": "J1", "company": "...", "title": "...", "level": "...", "status": "...", "applied_on": "YYYY-MM-DD or empty", "updated": "YYYY-MM-DD", "url": "...", "period": "optional, e.g. 2026H2"} ],
 "today": "YYYY-MM-DD",
 "expect": {"allowed": true|false, "counted": true|false, "period": "2026H2", "program": "intern|graduate|unknown", "used": 0, "remaining": 2},
 "quote": "spec sentence",
 "ambiguous": false
}
Omit fields that do not matter for the case ("url" may be ""). "used" and "remaining" matter only when counted is true.
