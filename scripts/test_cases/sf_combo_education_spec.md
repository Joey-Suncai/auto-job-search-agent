# SuccessFactors education rows made of combo lists (JSA-092, Erie 2026-11-04)

An application page has an education section whose repeated rows hold the boxes School, Degree, Major, Status and
Comments; School / Degree / Major / Status are drop-down lists. The resume parser creates these rows, often empty or
too many. Several small decisions turn the page into the right rows. Facts on file (profile order):

- Entry A: school "University of Chicago", short name "UChicago", level master, full degree "Master of Science",
  major "Applied Data Science", from 2026-09 to 2027-12, current (in progress).
- Entry B: school "University of Illinois Urbana-Champaign", short name "UIUC", level bachelor, full degree
  "Bachelor of Arts", major "Economics", ended 2026-05, not current.
- Today = 2026-11.

School names are compared by a normalized form: lower case, a trailing parenthesis group dropped ("(IL)", "(AZ / MO)"),
"&" read as "and", the words "the" and "at" dropped, then every character that is not a letter removed. So "The
University of Chicago", "University of Chicago (IL)" and "UNIVERSITY OF CHICAGO" are Entry A; "University of Illinois at
Urbana-Champaign (IL)" and "University of Illinois - Urbana Champaign" are Entry B; "UChicago" / "UIUC" (the short names)
also count. A name that merely contains the school ("Loyola University Chicago", "University of Illinois Chicago",
"University of Chicago Laboratory Schools") is NOT that school in the list pick (rule 3).

Placeholders are never real options or values: "No Selection", "Select", "Select One", "Please select", "-", "---",
"There were no results", "No results", "No results found", "No matches", "Loading…".

1. group_rows(fields): fields = the page's boxes in page order, each {key, label, type ("combo"/"text"/"textarea"),
   value}. A row starts at a box labelled "School", "College", "University", "Institution", "School Name" or "Name of
   School" (a leading "*" and a trailing ":" in labels are ignored). The following boxes join that row while their label
   is an education-row label — at most 40 characters long and containing any of these as whole words: Degree, Major, Minor, Field of Study, Area of Study, Discipline,
   Subject, Status, Comment(s), Notes, GPA, Grade Point, Other, Specify, Not listed, School name, Institution name,
   Graduate/Graduation/Graduated, Start, End, From, Year, Month, City, State, Country, Location, Honors, Concentration.
   A row ends at the next
   School-type box (which starts a new row) or at the first box whose label is not an education-row label (e.g. "How did
   you learn about this job opportunity?", "First Name", "Email"). A row only counts when it contains a Degree or a Major
   box (labels "Degree", "Degree Type", "Major", "Field of Study" …); a lone School box is not a row. Output: the list of
   rows, each given as the list of its box keys in order.

2. row_plan(rows, edus): rows = [{school: <the School box value>, other: <the value of the row's companion box (rule 6)>}]
   in page order. A row's school text is its School value; when the School value starts with "Other", the companion
   value is the school text instead. A row is EMPTY when that text is empty or a placeholder (also "Other" with an empty
   companion). A non-empty row belongs to the entry whose normalized name (or short name) equals it; failing that, to
   Entry A when the text (letters only, lower case) contains "chicago", to Entry B when it contains "illinois".
   - The first row of an entry holds it; a later row of the same entry is deleted.
   - A non-empty row that belongs to no entry is "unmatched" (a person decides).
   - Empty rows, in page order, take the entries (profile order A, B) that have no row yet; empty rows left over are
     deleted.
   - Entries that still have no row are to be added.
   Output {rows: {"<row index>": school name of the entry it holds}, delete: [row indexes, ascending], add: [school names
   in profile order], unmatched: [row indexes]}. Row indexes start at 0.

3. pick_school(options, entry) → [option, "match"] when an option's normalized name equals the entry's school or short
   name; else [option, "other"] for an "Other" option — exactly "Other" first, then an option starting with "Other"
   (e.g. "Other - Not Listed"), then one containing "not listed" / "not found"; else [null, null]. Placeholders ignored.

4. pick_degree(options, entry) → the option equal (case-insensitive) to the entry's full degree name; else for a master
   entry the first option starting with "Master" (e.g. "Masters", "Master's Degree"), then one containing "Master",
   then one starting with "Graduate"; for a bachelor entry the first option starting with "Bachelor", then one
   containing "Bachelor"; else null.

5. pick_major(options, major) → the option equal to the major (case-insensitive); else the first option of two or more
   words whose words all appear in the major ("Data Science" for "Applied Data Science"), or that contains the whole
   major as a phrase ("Applied Data Science Program" for "Applied Data Science", "Economics and Finance" for
   "Economics"); else "Computer Science"; else "Information Systems" (also "Information System", "Computer Information
   Systems", "Management Information Systems"); else exactly "Other"; else null. A one-word option such as "Science" or
   "Data" never counts as the major. (Candidate's rule: no matching major → Computer Science, then Information Systems.)

6. companion(row boxes) → the key of the text / textarea box in the row whose label says "other", "not listed",
   "specify", "school name" or "institution name" (never a combo, never the GPA box); if none, the row's box labelled
   "Comments" / "Comment" / "Notes" / "Additional Information"; else null. When the school is not in the list the runner
   picks "Other" and types the school's name into this box.

7. pick_status(options, entry, today) → for a current entry the first option starting with "Attending", "Currently
   Attending", "Enrolled", "In Progress", "Pursuing" or "Current" that does not contain "no longer" or "not"; for an
   entry that ended on or before today the first option starting with "Graduated", "Completed", "Degree Awarded" or
   "Degree Received"; else null.

8. rebind(row, fields, taken): after the page re-renders, a read-back row {key, label} moves to another field only when
   its own key is no longer among the fields AND exactly one field with the same label exists whose key is not in
   `taken` (keys held by other rows); then that field's key; otherwise null (keep the key). Three boxes labelled
   "School" must never be collapsed into the first one.
