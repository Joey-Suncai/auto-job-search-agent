A JSON array of 16 cases: {"name", "fn": "desk_alive"|"should_notify", "args": {"state": {...} or null, "now": number,
"stale"?: number, "grace"?: number}, "expect": true|false}. Cover: fresh beat, beat exactly 60 s old, 61 s old, beat in
the future, string beat, non-numeric beat, null state; notify with no notified_at, notified 599 / 601 s ago, alive desk
(never notify), custom stale / grace.
