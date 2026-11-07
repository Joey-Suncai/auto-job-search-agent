# One apply desk at a time — spec (2026-11-05, JSA-182)
`desk_alive(state, now, stale=60)`: state is a dict (or null) that may hold "beat" (epoch seconds, a number or a numeric
string). True exactly when beat can be read as a number and now - beat <= stale (a beat in the future is fresh). Missing,
null or non-numeric beat → false.
`should_notify(state, now, stale=60, grace=600)`: false when desk_alive(state, now, stale); otherwise true when state has
no readable numeric "notified_at", or now - notified_at > grace; else false.
