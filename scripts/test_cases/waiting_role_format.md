One JSON object per case: {"name": str, "rows": [{"job_id": str|null (key may be absent), "folder": str, "kind": str}],
"applications": [{"job_id": str, "title": str|null (may be absent)}] | null,
"expect": [<expected role string for each row, in order>], "spec_quote": str, "ambiguous": false}
Write about 20 cases.
