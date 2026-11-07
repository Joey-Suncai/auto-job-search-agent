# Does a date read back from the form match the planned answer?

The plan holds the intended answer as text; the form's date box is read back as typed by the site. Return true when
they name the same date:
- Same numbers in any order/format: plan "06/14/2027" matches page "06/14/2027", "2027-06-14" and "14/06/2027".
- A plan given as "<Month name> <year>" (e.g. "December 2027", "Jun 2027") names a month: it matches a page date with
  three numbers when that month and year appear (e.g. "12/01/2027", "12/31/2027", "2027-12-01"), whatever the day.
  It does not match another month or year ("11/01/2027", "12/01/2028").
- An empty page value never matches.
