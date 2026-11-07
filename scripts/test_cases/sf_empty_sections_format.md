A JSON array of 22 cases: {"name": str, "sections": [{"id": str, "head": str, "empty": bool, "add": str}, …],
"expect": [ids], "spec_quote": str}. Mix single-section and multi-section cases; include the excluded headings in odd case
and with a leading "*", non-education sections (Previous Employment, References, Languages, Certifications, Licenses,
Skills), an education section that is not empty, one with add "", words that only contain "school" inside another word
(e.g. "Preschooler Care" is not a whole word "school" — expect not returned), and an empty input list.
