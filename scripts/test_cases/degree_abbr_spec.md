# Spec: degree_level check with an abbreviation prefix (JSA-282)

A form's degree field holds one option. The check says whether the option is acceptable for Joey, who holds a B.A. in
Economics (UIUC) and is earning an M.S. in Applied Data Science (UChicago). Either level is acceptable; which block it
belongs to is checked elsewhere.

Acceptable: a bare level (Masters, Master's, Master, MS, M.S., Bachelors, Bachelor's, Bachelor, BA, B.A., BS, B.S.,
Graduate, Undergraduate, Postgraduate, Master's Degree, Bachelor's Degree); a full degree name that is "Master ... of
Science", "Bachelor ... of Science", "Bachelor of Arts" (his real B.A.), "Master's / Bachelor's of Arts or Science";
"Masters (...)" / "Bachelors (...)".
Never acceptable (even if another rule would accept): anything with "Technology" (M.Tech, Master of Technology), an MBA
or "Master of Business Administration", a doctorate (Doctor, Ph.D.), an Associate degree.

New rule: many Workday tenants write options as "<abbreviation> - <full name>", e.g. "B.A. - Bachelor of Arts",
"M.S. - Master of Science", "BS – Bachelor of Science", "MBA - Master of Business Administration". The abbreviation is
1–6 letters with optional dots; the separator is a hyphen, en dash, colon, slash or bar with optional spaces. The check
then judges the full name after the prefix by the rules above, and the "never acceptable" rules apply to the whole
option text (prefix included). Text that is not of this form is judged as before. Matching ignores case.
