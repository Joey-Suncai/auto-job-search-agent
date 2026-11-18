One JSON object per case: {"name": str, "rows": [{"job_id": str|null (key may be absent), "folder": str, "kind": str}],
"jobs": [{"id": str, "tier": str (may be absent), "tier_orig": str (may be absent)}] | null,
"expect": [<expected tier string for each row, in order>], "spec_quote": str, "ambiguous": false}
Write about 20 cases.
