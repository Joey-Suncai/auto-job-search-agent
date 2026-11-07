# imap_since(since) — spec (gmail_code.py, 2026-11-03)

`since` is a Python datetime (given in the cases as an ISO 8601 string; with an offset such as "+00:00" / "-06:00",
or with no offset = naive). A naive value is taken as UTC. Convert `since` to UTC, subtract exactly one day, and
return that UTC date formatted as "DD-Mon-YYYY" with a two-digit day and the English three-letter month with a capital
first letter (e.g. "03-Nov-2026", "31-Dec-2025"). The time of day only matters through the conversion to UTC.
