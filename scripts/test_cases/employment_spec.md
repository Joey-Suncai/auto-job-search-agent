# Greenhouse Employment section — spec (JSA-228)

The newer Greenhouse application form has an "Employment" section. Block N (N = 0, 1, …) has these fields:
company-name-N (text), title-N (text), start-date-month-N (a month list), start-date-year-N (text),
end-date-month-N (a month list), end-date-year-N (text), and a checkbox current-role-N ("Current role", never required).

## employment_fields(blocks, required)
Returns the field descriptors of blocks 0 … blocks-1 in that order, 7 per block, in the order company, title,
start_month, start_year, end_month, end_year, current. Each: key (as above), label ("Company name", "Title",
"Start date month", "Start date year", "End date month", "End date year", "Current role"), type ("text" for company,
title and the years; "combo" for the months; "checkbox" for current), required (= `required` for every field except the
current box, which is always False), options [], sel (`[id="<key>"]`, except the current box: `[name="<key>"]`),
emp = N, emp_kind (company / title / start_month / start_year / end_month / end_year / current).
blocks 0 or negative → [].

## employment_entries(work)
Input: the profile's work list; each entry {Company, Job Title, From, To, current}. From / To are "MM/YYYY" (one or two
digit month) or "YYYY-MM". Output: one dict per entry with a non-empty Company: {company, title, start_month,
start_year, start_num, end_month, end_year, end_num, current}. company / title = the stripped strings (title '' when
missing). *_month = the English month name ("August"), *_year = the year string, *_num = the month as two digits
("08"); all three '' when the date is missing, not in one of the two formats, or the month is not 1–12.
current = True only when `current` is the boolean true (the string "true" is not).
Order = most recent first: entries with current true first, then by From date newest first; entries without a usable
From come last; ties keep the input order.

## employment_answer(f, entries)
f = one descriptor from employment_fields; entries = employment_entries output. Returns a copy of f with answer /
status / source added. Block N uses entries[N]; when there is no entries[N], nothing is invented: status "needs_user"
when f is required, else "skip_optional"; no answer. Otherwise:
- current box: answer = the entry's current (True / False), status "ok".
- end month / end year of a current entry: status "skip_current", no answer (left empty).
- any other field: answer = the entry's value for that kind (company, title, start_month, start_year, end_month,
  end_year), status "ok", source "profile.work". An empty value → "needs_user" if required, else "skip_optional", no answer.
- a month field that is answered also gets alts = [3-letter month name, two-digit number, number without the leading
  zero] with duplicates and the answer itself removed, accept = [answer] + alts, and month_num = the two digits.
  Example: August → alts ["Aug", "08", "8"]; October → alts ["Oct", "10"]; May → alts ["05", "5"] ("May" is the answer).

## month_text_answer(name, num, input_type, maxlength, placeholder)
The value typed when the month is a plain input box instead of a list: input_type "number" → the number without the
leading zero ("8"); else maxlength 1 or 2, or a placeholder that is just "MM" or "M" (any case, spaces allowed) → the
two digits ("08"); otherwise the month name ("August"). maxlength may be None, '' or a non-number string (= no limit).
