Each case is a JSON object:
{
 "name": "short id",
 "sources": [ {"source": "...", "type": "...", "cadence": "...", "last_run": "2026-10-23", "in_dashboard": 5, ...} ],
 "jobs": [ {"id": "J1", "sources": "A; B"} ],      // sources may be a string, a list, or absent
 "today": "2026-11-03", "github_ok": true, "boards_ok": true,
 "expect": [ {"source": "...", "type": "...", "cadence": "...", "last_run": "...", "in_dashboard": 2, ...} ],  // full expected output, in order
 "spec_quote": "the sentence(s) of the spec this case tests",
 "ambiguous": false
}
