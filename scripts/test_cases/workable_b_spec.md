# run_workable.py — spec part 2 (JSA-122, Workable CA_ fields)

## plan_fields(form)
Pure (tested). The form schema (a list of sections {name, fields:[{id, type, required, label, choices}]}) → the fields to answer: [{key, label, type, required, options}] in page order. `group` fields (Education / Experience lists) and the photo (`avatar`) are skipped; `resume` / other files keep type 'file'; boolean → options ['Yes', 'No']; otherwise the option texts come from `choices` (each `body`, else `name`) or, for the company's own `CA_` fields, from `options` (each `value`, else `name`).

## choice_map(form)
Pure (tested). The form schema → {field id: {option text: option id}} for fields with choices / options: the id is what the page's radio carries as its value — a choice's `id` (else `name`), an option's `name` (else `value`). Booleans map Yes → 'true', No → 'false'. Fields without options are left out.

Type map for plan_fields (schema type → plan type): text→text, email→text, phone→text, paragraph→textarea, boolean→radio, multiple→radio, dropdown→select, date→date, numeric→text, file→file, group→(skipped); any other type → text. Labels and option texts have whitespace collapsed and trimmed; required is a boolean (missing → false). Option ids in choice_map are strings.
