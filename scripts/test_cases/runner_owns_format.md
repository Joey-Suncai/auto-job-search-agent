Return a JSON array. Each case:
{"name": "snake_case", "mark": {"ts": 1000, "pid": 42, "phase": "submit"} or null or any JSON value,
 "now_ts": 1500, "alive_pids": [42], "expect": true}
alive(pid) returns true exactly when pid is in alive_pids. About 1/3 expect true. Cover each boundary in the spec.
