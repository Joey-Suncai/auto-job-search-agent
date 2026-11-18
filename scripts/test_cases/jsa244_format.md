A JSON array of about 30 cases, each with "name", "fn", "spec_quote" and:
- fn "skipped": "company": str|null, "names": [str]|null, "expect": bool                       (about 5)
- fn "pending": "sheet": <any JSON>, "handled": list|null|{name: [texts]|null}, "expect": [ids]  (about 7, dict form mostly)
- fn "rules": one form field run through the full rule set with the example profile above (a fictional candidate who
  never worked at a Greenhouse employer, Acme or Globex; no saved answers): "field": {"label": str, "type": "combo"|"multi"|"radio"|
  "checkbox"|"text", "options": [str]}, "expect_status": "ok"|"unknown", "expect_value": str|null (only for ok),
  "expect_ask": true|false|null (only for unknown; null = do not check)                            (about 18: language
  lists, native/first-language single choice, level for Spanish / English / German / unnamed CEFR, none options,
  certification options, programming-language near misses, and the "No" statement-list cases incl. two negatives)
