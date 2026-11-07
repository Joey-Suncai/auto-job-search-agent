# Ashby runner: dates written in words, the School type-ahead, and errors shown after Submit (JSA-208 / JSA-209)

Four small pure functions of the Ashby form runner.

## 1. date_same(want, got) → true / false
`want` is the planned answer for a date box, `got` the text the date box shows after filling. Ashby date boxes show
dates as MM/DD/YYYY. Return true when they name the same date:
- Same numbers in any order/format: want "06/14/2027" matches got "06/14/2027", "2027-06-14" and "14/06/2027".
- A want written with the month as a word and a day ("June 14, 2027", "Jun 14 2027", "14 June 2027", "June 14th, 2027")
  or as YYYY-MM-DD names that full date: it matches got "06/14/2027" (and the other forms above), never another day,
  month or year ("06/15/2027", "07/14/2027", "06/14/2028").
- A want given as "<Month name> <year>" (e.g. "December 2027", "Jun 2027") names a month: it matches a got date with
  three numbers when that month and year appear (e.g. "12/01/2027", "12/31/2027", "2027-12-01"), whatever the day.
  It does not match another month or year ("11/01/2027", "12/01/2028").
- An empty got never matches. A want that is not a date at all ("Summer 2027", "ASAP") matches only exactly the same
  text (case and spaces ignored).

## 2. date_value(want) → [value, reason]
What the runner types into an Ashby date box for the planned answer `want` (a plan may have been written before the
answer was checked, so the runner checks it again):
- A full date in any unambiguous form → [MM/DD/YYYY with two-digit month and day, null]: "June 14, 2027" →
  ["06/14/2027", null]; "6/4/2027" → ["06/04/2027", null]; "2027-06-14" → ["06/14/2027", null]; "14 June 2027" →
  ["06/14/2027", null]; "06/14/2027" stays ["06/14/2027", null].
- "<Month name> <year>" ("December 2027") is kept as it is: ["December 2027", null].
- Anything else → [null, reason] where reason is a non-empty text: a season ("Summer 2027"), a day-first date whose
  first number is above 12 ("14/06/2027"), a date that does not exist ("02/30/2027", "June 31, 2027"), free text ("ASAP"),
  an empty string.

## 3. pick_school(options, school) → index or null
The education "School" box is a type-ahead: after typing the school's name a list of options appears. `options` is the
list of option texts as shown (in order), `school` the school name from the candidate's profile. Return the 0-based
index of the option to click, or null when no single option is the school (the runner then asks the candidate and
does not guess). Names are compared after lower-casing, turning "&" into "and", removing punctuation (commas,
periods, hyphens, apostrophes, parentheses become spaces), collapsing spaces and dropping a leading "the".
- An option equal to the school after that normalisation wins ("The University of Chicago" and "university of
  chicago" are both the school "University of Chicago"); when several are equal, the first of them.
- Otherwise, when exactly one option contains the whole normalised school name as a run of whole words (e.g.
  "University of Chicago (Chicago, IL)" for "University of Chicago"), that option. Two or more such options (e.g.
  "University of Chicago Booth School of Business" and "University of Chicago Laboratory Schools") → null.
- A name that only shares words is not the school: "Loyola University Chicago" and "Chicago State University" are not
  "University of Chicago"; "University of Illinois Chicago" is not "University of Illinois Urbana-Champaign".
- An empty option list or an empty school → null.

## 4. submit_errors(text) → list of strings
`text` is the visible text of the Ashby page (lines separated by "\n") read after the runner pressed "Submit
Application". When Ashby refuses the form it shows a red box headed "Your form needs corrections" with one line per
problem, e.g. "Missing entry for required field: School". Return what the box lists, in order; [] when the page shows
no such errors (for example the thank-you page, or the form before Submit):
- A line "Missing entry for required field: <Field>" anywhere on the page gives "<Field>" (the field name alone,
  trimmed).
- After the heading "Your form needs corrections", each following non-empty line that reads as an error message
  (it contains "required", "invalid", "must", "please enter", "please select", "not valid" or "missing", case ignored)
  is part of the list; the first non-empty line that is not an error message ends the list. A "Missing entry …" line in
  the list gives the field name as above; other lines are returned whole (trimmed).
- The heading with no error line after it gives ["form needs corrections"].
- A field label that ends in "*" (a required marker) is not an error; text such as "Thank you for applying" is not an
  error; the same field is listed once.
