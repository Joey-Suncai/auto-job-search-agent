Each case is a JSON object with "name", "kind", "spec_quote", "ambiguous" and the fields for its kind:

kind "should_write":
 {"ats": "lever", "status": "dry-run", "problems": ["..."], "results": [{"ok": true}, ...], "expect": true | false}

kind "sheet":
 {"folder": "/abs/path/2026-10-31_Acme_Intern",
  "plan_fields": [{"key": "name", "label": "Full name"}, ...],
  "results": [{"key": "name", "label": "Full name", "type": "text" | "textarea" | "file" | "radio" | "select" | "checkbox", "want": "..." or null, "ok": true}, ...],
  "expect_rows": [["<Field column>", "<Answer column>"], ...]   // in order; for a file row write the absolute path only;
                                                               // for a long answer write "LONG"; answers exactly as shown (escaped "\|", spaces for line breaks)
  "expect_blank": ["label", ...],          // labels under Leave blank, in order
  "expect_files": ["/abs/path/file.pdf"],  // paths under Files, in order
  "expect_long": [{"n": 3, "text": "full original text"}],
  "expect_command_folder": "2026-10-31_Acme_Intern"}

kind "manual_line":
 {"folder": "f1", "results": [{"folder": "f1", "status": "dry-run"}, ...], "url": "u", "ats": "lever", "at": "2026-10-31T15:00:00",
  "note": "" or "text" or null,
  "expect": null or {"folder": "f1", "url": "u", "ats": "lever", "at": "...", "status": "submitted", "by": "joey", "note": "..."}}

Write about a third of the cases per kind.
