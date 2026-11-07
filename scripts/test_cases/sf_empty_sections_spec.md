# Which empty SuccessFactors sections get one row added before the education rows are filled — spec (2026-11-05, Erie)

Function `sections_to_open(sections)` takes the visible sections of a SuccessFactors application form, each
`{"id": str, "head": str, "empty": bool, "add": str}` — `head` is the section heading, `empty` is true when the section
shows "There are no items in this section", `add` is the id of the section's visible "Add" control ("" when none).
It returns the list of `id`s (in input order) whose Add is clicked once, so the runner can then fill the new row.
A section is returned only when ALL hold:
1. `empty` is true;
2. `add` is a non-empty string;
3. the heading is about education: it contains (case-insensitive, as a whole word) "education", "degree" / "degrees",
   "school" / "schools" / "schooling", or "academic";
4. the heading (after trimming spaces and a leading "*") is NOT exactly "Education", "Formal Education" or
   "Education History" (any case) — another module adds those sections' rows itself.
Everything else (work experience, references, languages, certifications, licenses, a section with rows, a section with
no Add control) is not returned. Examples of headings that ARE returned: "Highest Level of Education Completed",
"Education Details", "Degrees", "Academic Background", "School Information".
