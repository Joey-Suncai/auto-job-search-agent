# JSA-272 — two Workday runner functions (pure)

## zero_rejected(errs, fields) → list of fields
`errs` is a list of Workday page-error strings. `fields` is a list of dicts with at least "label" and "answer".
An error of the form "Error: The field <Q> is required and must have a value." (whitespace inside may be doubled, case
of the words does not matter) names a question Q. A field is returned when its label equals Q after collapsing whitespace
and lower-casing both sides, AND its answer is a zero written in digits: "0", "00", "0.0", "0.00" (leading/trailing
spaces allowed). Answers like "", "52000", "10", "0.5", "N/A", "zero" or None do not count. Errors of any other wording are
ignored. A question matched by no such field adds nothing. The result keeps the order of `errs`; for each error at most
one field (the first matching one in `fields` order).

## block_kind_of(section) → "languages" | "education" | "work" | None
A Workday repeat-block heading. Checked in this order, case-insensitive substring/word tests:
1. contains "language" → "languages"
2. contains "educat" or "academic", or the whole word "school" / "schools" → "education"
3. contains "work", "experience" or "employment" → "work"
otherwise None. Examples: "Schools Attended 3" → education; "Academic Experience 1" → education (rule 2 wins over 3);
"Where have you worked? 2" → work; "Fluent Languages 1" → languages; "Preschool teacher" → None ("preschool" is not the
whole word school); "Personal Information" → None.
