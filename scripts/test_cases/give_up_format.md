One JSON object per case, with "fn" one of:
- "decline": {"name", "fn":"decline", "row": {...}, "give_up": bool, "today": "YYYY-MM-DD", "expect_row": {...full expected row}, "expect_error": str|null, "spec_quote": str}
- "validate": {"name", "fn":"validate", "method": str, "path": str, "headers": {lower-case keys}, "body": str (JSON text), "expect_code": int, "expect_payload": {...} (only for 200), "spec_quote": str}
- "todo": {"name", "fn":"todo", "apps": [tracker rows with job_id, company, status, action_needed], "today": "2026-11-17", "expect_job_ids": [job ids of the resulting to-do rows, in order], "spec_quote": str}
- "echo": {"name", "fn":"echo", "apps": [rows with job_id, status, applied_on "2026-11-01"], "expect": {"<job_id>": declined 0 or 1 for each record that is produced}, "spec_quote": str}
Write about 30 cases (about 18 decline, 8 validate, 2 todo, 2 echo).
