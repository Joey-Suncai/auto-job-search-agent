Return {"cases": [...]}. Each case is one of:
{"name": str (unique), "fn": "audit", "label": str, "value": str, "expect_mismatch": true | false, "expect_reason": "empty" | null, "spec_quote": str, "ambiguous": false}
  (expect_mismatch = whether an education_field mismatch is returned; expect_reason only when true)
{"name": str (unique), "fn": "load_reasons", "lines": [str, ...] (raw JSONL lines, may include a malformed one), "key": str,
 "expect": {"status": str, "value": str, "reason": str, "kind": "canon" | null}, "spec_quote": str, "ambiguous": false}
Write about 26 cases: 16 audit (8 second-major labels incl. "Education (UIUC): Secondary Major", "Minor", "Double Major",
"Major 2", "Additional Field of Study", none-like values and empty; 2 "major and minor" near misses with empty value;
3 main-major empties incl. "Field of Study"; 3 main majors with Data Science); 10 load_reasons (canon then plain same
value; canon then plain different value; plain then canon; two plains; canon then canon; malformed line in between;
other keys interleaved).
