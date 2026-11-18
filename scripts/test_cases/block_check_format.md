A JSON array of 28 cases. Each case is ONE form:
{"name": str, "rows": [{"label": str, "page": str, "source": str (optional), "section": str (optional), "kind": str (optional)}, ...],
 "expect": [verdict for each row in the same order: "ok" | "bad" | "unknown" | null]}
null = the row is not part of any block (a lone question, a contact field).
Cover: Workday blocks with no section (two education blocks one after the other, two work blocks), Workday with sections
("Education 1"), SuccessFactors prefixed labels ("Education (UIUC): Degree", "Previous Employment (Frost & Sullivan): Title"),
Greenhouse rule rows (School / Degree / Discipline / Start date month / Start date year / End date month / End date year),
the major GPA 3.85 in UIUC's "Overall Result (GPA)" (bad), "Major GPA" 3.85 (ok), a GPA in the UChicago block (bad),
"Job Searching Agent" as the Hyde Park Job Title (bad), a résumé-parsed description of another project (bad), swapped
degrees (bachelor option in the UChicago block), swapped fields, wrong years and months, "I currently work here" checked,
still-attending / degree-achieved boxes, upper-case school / company names, a lone "What is your GPA?" question (null),
an unknown box (Minor, Division).
