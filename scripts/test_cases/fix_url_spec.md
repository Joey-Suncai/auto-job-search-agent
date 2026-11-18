# Spec: completing a bare web address for a box that wants a full URL (JSA-312)

fix_url(value, wants_url) → the text to type.
- wants_url is true when the form box asks for a web address (type=url, a "format: http://example.com" hint, or a label
  that is only a link name such as "Link 1", "Website", "LinkedIn Profile", "GitHub", "Portfolio").
- When wants_url is true and the value (trimmed) is a bare web address — an optional "www.", a host name with at least
  one dot and a top-level domain of 2+ letters, optionally followed by a path with no spaces — and it does not already
  start with http:// or https:// (any case), the result is "https://" + the trimmed value.
- Otherwise the value is returned unchanged (exactly as given, untrimmed): already a full URL, not an address ("N/A",
  "None", "see resume", "my LinkedIn"), an e-mail address ("joey@example.com" is not a web address), text with spaces,
  an empty string, or wants_url false.
