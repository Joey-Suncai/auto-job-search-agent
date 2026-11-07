Each case is a JSON object:
{
 "name": "short id",
 "pairs": [ {"q": 1, "a": {"id": "J1", "role": "pm", "sponsor": "some", "green_card": false},
                     "b": {"id": "J2", "role": "data", "sponsor": "some", "green_card": false}} ],   // optional "repeat_of": q
 "answers": {"1": "A"},
 "prior_sd": 2,
 "model": "buckets" | "v1",      // optional, default buckets; v1 cards carry "h1b_fy25"
 "loo_all_predicted": true,      // optional: leave-one-out must predict every choice
 "expect": {
   "positive": ["role:pm"],          // weights that must be > 0 (feature names: role:<r>, sponsor:<s>, green_card)
   "negative": [],                   // weights that must be < 0
   "zero": [],                       // weights that must be exactly 0 (|w| < 1e-9)
   "greater": [["role:ai_pm", "role:pm"]],   // pairs [x, y]: weight x > weight y
   "n_choices": 1,
   "consistency_same": [true]        // `same` values in order (omit to skip)
 },
 "spec_quote": "...",
 "ambiguous": false
}
