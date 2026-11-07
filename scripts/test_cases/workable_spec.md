# run_workable.py — spec (JSA-122)

## parse_posting(url)
Pure (tested). 'https://apply.workable.com/<account>/j/<SHORTCODE>/…' → {'account', 'shortcode'} or None.

## plan_fields(form)
Pure (tested). The form schema (a list of sections {name, fields:[{id, type, required, label, choices}]}) → the fields to answer: [{key, label, type, required, options}] in page order. `group` fields (Education / Experience lists) and the photo (`avatar`) are skipped; `resume` / other files keep type 'file'; boolean → options ['Yes', 'No']; choices → their `body` (or `name`) texts.

Type map (schema type → plan type): text→text, email→text, phone→text, paragraph→textarea, boolean→radio, multiple→radio, dropdown→select, date→date, numeric→text, file→file, group→(skipped); any other type → text. Labels have whitespace collapsed and trimmed; required is a boolean (missing → false).
