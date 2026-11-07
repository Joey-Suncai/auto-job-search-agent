Return {"cases": [...]}. Each case: {"name": str, "fn": "degree_option" | "tenant_id" | "code_mail_ok" | "box_fit" | "edu_fill", "args": {...}, "expect": ..., "spec_quote": str, "ambiguous": false}.
degree_option: args {"want": str, "options": [str]}, expect str | null.
tenant_id: args {"url": str}, expect str.
code_mail_ok: args {"sender": str, "body": str, "tenant": str, "company": str | null}, expect true | false.
box_fit: args {"label": str, "kind": str, "value": str | null, "box": object}, expect "not_number" | "too_long" | null.
edu_fill: args {"school": str, "education": [{"school", "match_re"?, "level", "current"?, "end", "city"?, "state"?}], "today": "YYYY-MM-DD"}, expect null or {"city", "state", "graduated": "Yes"|"No", "degree", "school"?} — include "school" only in the fallback case.
Write 30 cases: degree_option 6, tenant_id 5, code_mail_ok 7 (other tenant's code, own tenant, company sender naming / not naming the company, no company), box_fit 7, edu_fill 5 (split letters, fallback by level + end month, two entries matching → null, wrong month → null).
