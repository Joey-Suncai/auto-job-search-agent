Each case is a JSON object:
{"name": "short_snake_case", "fn": one of "outcome" | "build_sample" | "normalise" | "fit_map" | "spearman" |
 "ranking_change" | "needed_n", "input": {...}, "expect": {...}, "spec_quote": "...", "ambiguous": false}

input / expect per fn:
- outcome: input {"status": string or null}; expect {"value": 1 | 0 | null}
- build_sample: input {"apps": [...], "jobs": {id: {s_referral, s_timing, s_sponsor, s_fresh}}, "today": "YYYY-MM-DD",
  "min_days": int}; expect {"n": int, "ys": [list of y in input order of used rows], "xs": optional list of x lists,
  "excluded": optional {reason: count}}
- normalise: input {"beta": [4 numbers]}; expect {"weights": [4 numbers], tolerance 1e-6}
- fit_map: input {"rows": [{"x": [4], "y": 0|1}], "mu": [5], "sd": [5]}; expect any of
  {"equals_mu": true}, {"cov_diag_equals_sd2": true}, {"positive": [factor index 1..4]}, {"negative": [index]},
  {"pinned": [index 0..4]} (coefficient within 1e-3 of mu), {"var_le_prior": true}, {"finite": true}
- spearman: input {"a": [...], "b": [...]}; expect {"value": number, tolerance 1e-6}
- ranking_change: input {"jobs": [{id, elig, v_level, s_referral, s_timing, s_sponsor, s_fresh}], "w_old": {..4 keys},
  "w_new": {...}, "top": int}; expect any subset of {"n", "spearman", "top_overlap", "b_c_flips", "c_to_b", "b_to_c"}
- needed_n: input {"rows": [...], "beta": [5], "prior_sd": number}; expect {"none": [factor names that must be None],
  "int": [factor names that must be positive ints]}
