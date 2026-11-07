# Muting pushes — spec (2026-11-05, JSA-181)
`muted(env)` takes a dict of environment variables and returns true exactly when the key JSA_NO_PUSH is present and its
value, with surrounding spaces removed, is neither "" nor "0". Any other value ("1", "yes", "true", "false", " 2 ") mutes.
`notify(title, body)` when muted: shows and sends nothing (no notification, no iMessage, no osascript call at all) and
returns an empty list. When not muted it tries the Mac notification (and iMessage when configured).
