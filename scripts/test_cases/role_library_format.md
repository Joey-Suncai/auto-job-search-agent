Return a JSON array of cases. Each case has "name", "why", "fn" and fields for that function:
- fn "matcher": {"term": "SQL" or {"t":"R","cs":true}, "text": "...", "expect": true|false}
- fn "split_req": {"text": "...", "expect_required": "exact required part", "expect_preferred": "exact preferred part"}
- fn "stats": {"texts": ["jd1", ...], "lexicon": {"competencies": {"cid": {"label": "L", "keywords": [["canon","syn"], ...]}}},
     "expect": {"cid": {"df": 0.5, "req_share": 1.0, "weight": 0.6667, "keywords": {"canon": {"df": 0.5, "req_share": 1.0}}}},
     "expect_order": ["cid_first", "cid_second"]}   (expect may list only some competencies / keywords; numbers compared at 3-4 decimals)
- fn "select": {"jobs": [...], "texts": {...}, "selector": {...}, "expect": ["id", ...]}
Write about 8 matcher, 5 split_req, 8 stats, 6 select cases. Use small texts so the numbers can be computed by hand; show the arithmetic in "why".
