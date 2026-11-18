# SmartRecruiters page 1: required work experience + month pickers (JSA-233)

Some SmartRecruiters forms require at least one work experience entry on page 1 ("Please provide at least one work
experience entry"); Next is refused until one is saved. The runner adds the candidate's work entries only when the form
config says the Experience section is required. Five pure helpers:

## picker_ym(value) → "YYYY-MM" or null
What a month-picker box holds, normalised. Accepted forms: an ISO date "YYYY-MM-DD" (what the box holds today, e.g.
"2026-09-01" → "2026-09"), "YYYY-MM", and "MM/YYYY" (month may be one digit: "9/2026" → "2026-09"). Leading/trailing
spaces are ignored. The month must be 1–12, else null. Anything else (empty, null, "Sep 2026", "2026", "09-2026",
"2026/09") → null. The day part is not checked beyond being 1–2 digits.

## ym_of(value) → "YYYY-MM" or null
A profile date ("2025-08", "08/2025", "2025-08-01") → "YYYY-MM"; same rules as picker_ym.

## experience_required(cfg) → bool
cfg is the form config JSON: {"fieldSets": {"experience": {"required": bool, "visible": bool}, ...}}. True only when
fieldSets.experience.required is true and visible is not false (a missing "visible" counts as visible). Missing
fieldSets, missing experience, null cfg → false.

## exp_entries(work) → list
work is a list of profile entries {"Job Title", "Company", "Location" ("City, State" or "City, Country"), "From"
("MM/YYYY"), "To" ("MM/YYYY"), "current" (bool), "Description"}. Output, one dict per usable entry:
{"title", "company", "city", "description", "start", "end", "current"} where title/company are the trimmed values with
runs of whitespace collapsed to one space, city = the Location part before the first comma (trimmed; "" when there is no
Location), description = Description trimmed ("" when missing), start = ym_of(From), end = ym_of(To) — but null when
current is true, current = bool(current). An entry without a title, without a company, or whose From is not a valid date
is left out (never guessed). An invalid To on a non-current entry gives end null (the entry is kept). Sorted by start,
most recent first. Empty / null work → [].

## location_option(city, options) → str or null
The autocomplete option to click for a city: the first option whose text (whitespace collapsed, trimmed) starts with
"<city>," compared case-insensitively (city trimmed, whitespace collapsed). Never an option starting with "Cannot find"
(the "Cannot find your city? Click here to fill in manually" entry). Returns the option text whitespace-collapsed and
trimmed. Empty city, no options, or no match → null. "Chicago" must not match "Chicago Heights, IL, US" (the comma
must follow the city name directly).
