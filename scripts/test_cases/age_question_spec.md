# Age-band question recognition — spec (2026-11-05, JSA-213)

An application form question (label text + a list of choice options) is an "age band" question when it asks the
applicant's CURRENT AGE or AGE RANGE as a demographic question, and should then be answered by picking the option whose
numeric band contains the applicant's age (age 23 in these cases). Recognised labels (case-insensitive, a trailing "?"
optional, the whole label being exactly one of these):
- "Age", "Current age"
- "Your age", "Your current age", "What is your age", "What is your current age", "What's your age",
  "What's your current age"
- "How old are you"
- or any label containing "age range", "age group", "age bracket" or "age band" as words (e.g. "What is your age range?",
  "Please select your age group").
NOT age-band questions (the age-band rule must not answer them): eligibility questions such as "Are you at least 18
years of age?", "Are you under the age of 18?", "Are you 18 years of age or older?", "Are you of legal working age?",
questions about a date of birth, "average", "language", "page", "manager", "stage", "wage", "agency" or other words
that merely contain the letters "age", and a recognised label inside a longer sentence that is not one of the forms
above (e.g. "Do you have an age requirement for travel?").
For a recognised question the expected answer is the option whose band contains 23 ("Under 30", "18-24", "21-29",
"20 to 29" …); when no option contains 23 the expected answer is "" (unknown).
