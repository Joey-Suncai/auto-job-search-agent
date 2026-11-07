Each case is a JSON object:
{
 "name": "short id",
 "staged": ["paths staged in this commit"],
 "backlog_before": {"JSA-001": "todo"},      // Status per row in the committed BACKLOG.md ({} if not relevant)
 "backlog_after":  {"JSA-001": "done"},      // Status per row in the staged BACKLOG.md ({} if not staged)
 "results_new_submitted": [{"folder": "2026-10-31_X", "job_id": "J00001" or null, "in_tracker": true}],  // newly added submitted lines
 "results_other_new_lines": 0,               // number of newly added lines with another status
 "session_log_today_exists": true,
 "expect": "pass" | "block",
 "expect_errors": ["which rule numbers give an ERROR, e.g. 1, 4"],
 "expect_notes": ["rule numbers that give a NOTE"],
 "spec_quote": "the sentence(s) of the spec this case tests",
 "ambiguous": false
}
Focus: rule 8 (config/profile.json ↔ cx_bundle.js), alone and together with rules 2, 4 and 7, plus files under config/ other than profile.json.
