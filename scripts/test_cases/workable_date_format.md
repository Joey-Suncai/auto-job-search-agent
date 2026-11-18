Each case is a JSON object:
{"name": "<short unique snake_case name>", "fn": "parse_date" | "to_mask" | "same_date",
 "args": {"s": "..."}                      for parse_date
       | {"value": "...", "placeholder": "..." or null}   for to_mask
       | {"want": "...", "got": "..."}     for same_date,
 "expect": [y, m, d] or null (parse_date) | "string" or null (to_mask) | true/false (same_date),
 "spec": "<the spec sentence>", "ambiguous": false}
Mix the three functions (about 8 parse_date, 12 to_mask, 5 same_date). Include the Syntiant case: to_mask("06/14/2027", "YYYY/MM/DD").
