# Certification bar per platform

bar_for(name) returns the bar a platform must meet, as an object with keys n, no_joey, clean, confirm, secs, cost.
Default for every platform: n = 50 submitted, no_joey = 0.95, clean = 0.95, confirm = 0.95, secs = 300, cost = 0.01.
Exception (Joey 2026-11-02): "lever" needs n = 30, and its no_joey is null (reported for information only, not a bar,
because the last step — Submit past hCaptcha — is done by hand). All other keys of "lever" keep the default.
The name is matched exactly (lower case, as stored): "Lever" or "lever " are not "lever"; unknown names get the default.
