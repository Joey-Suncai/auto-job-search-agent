A JSON array of 24 objects, each:
{"name": "<short unique snake_case>", "label": "...", "required": true|false, "kind": "text"|"textarea",
 "limits": {"max": int|null, "min": int|null, "format": "url"|null} | null, "source": "rule"|"draft",
 "answer": "..." | {"repeat": "...", "times": n}, "page_invalid": bool, "page_error": "...",
 "expect": "stop_ask"|"leave"|"redraft"|"fill"|"page_stop", "expect_limit": int|null, "expect_min": int|null}
expect_limit / expect_min only for "redraft" (else null). Use {"repeat"} for answers over 150 characters. Draft cases must
use essay labels (longer than 100 characters, or starting with Describe / Tell us / Share / Explain) and kind textarea.
Cover the an employer replay rows, optional vs required, min vs max, url by format and by label, drafts with and without a
known max, whitespace padding, and page errors after an answer that fit.
