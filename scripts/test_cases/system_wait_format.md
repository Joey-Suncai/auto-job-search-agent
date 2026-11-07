Return a JSON array. Each case is one of:
{"name": "snake_case", "fn": "system_fields", "plan": {"ats": "ashby", "fields": [{"key": "_systemfield_name", "status": "ok"}]}, "expect": ["_systemfield_name"]}
   (expect = the keys of the returned fields, in order)
{"name": "snake_case", "fn": "wait_until", "keys": ["a", "b"], "appear_at": {"a": 0, "b": 3.0}, "timeout": 5, "step": 1, "expect": [], "expect_sleeps": 3}
   Simulated time: the clock starts at 0 and only sleep(step) advances it by step. Key k is present when the current
   time >= appear_at[k]; a key missing from appear_at never appears. expect = the returned list; expect_sleeps = how many
   times sleep was called.
About half of each kind.
