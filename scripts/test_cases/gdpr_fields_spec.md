# Greenhouse GDPR consent boxes from the public job API

The Greenhouse job API returns `data_compliance`: a list of objects. Only entries with `"type": "gdpr"` matter; others
(e.g. "eeoc") add nothing. A gdpr entry has booleans `requires_consent`, `requires_processing_consent`,
`requires_retention_consent`, `demographic_data_consent_applies`.
For each gdpr entry, the form shows these checkboxes, in this order:
- `gdpr_processing_consent_given` when `requires_processing_consent` is true — required.
- `gdpr_retention_consent_given` when `requires_retention_consent` is true — required.
- `gdpr_demographic_data_consent_given` when `demographic_data_consent_applies` is true — not required.
`requires_consent` alone adds nothing. Missing or empty `data_compliance` → no boxes. The same box is never listed twice,
even if two gdpr entries ask for it. Output: the list of [name, required] pairs.
