Return a JSON array of test cases. Each case:
{
  "name": "short_snake_case_name",
  "why": "one sentence: what this case tests",
  "facts": {"entries": [...], "facts": [...]},
  "bank_md": "## Org Name\n- bullet text\n  *used in: X · tags: y*\n",
  "expect": "pass" | "fail",
  "expect_problems": ["schema" | "number_drift" | "no_entry" | "unmapped" | "unsupported_number" | "never_phrase", ...]
}
expect_problems lists each problem KIND that must appear (a set, no duplicates); empty for "pass".
When a schema problem exists, only "schema" is expected (the bank is not checked then).
Use fictional people and organisations. Mix: about 1/3 pass cases, the rest each targeting one or two kinds; include tricky ones
(numbers with commas / currency / percent / ranges, anchors in different case, never-phrases inside longer words that must NOT match,
a heading that only partially matches an org, decimals like 2.169 vs 2.17).
