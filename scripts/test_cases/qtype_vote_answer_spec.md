# Haiku re-read compared by ANSWER, not by key (JSA-361 v2b)

A reading has `fact_key`, `shape`, `negated` (missing = false), `subject`, `confidence`. A reading **asks** when fact_key is
"none" or "unknown", confidence "low", shape "unclear" or "trap", subject "unclear", or subject "other_person" with a key
not in: referral, references, relatives, relative_names, know_employee, contact_employer.

`facts` maps a fact key to its value: any of `{"yes": true|false}`, `{"text": "..."}`, `{"pick": ["pattern", ...]}`.

## The answer a reading leads to
- a reading that asks → no answer;
- fact key not in facts → the answer is "the key itself" (only the same key, shape and negated give the same answer);
- shape yes_no, choice, multi_choice, subscription, data_consent or attestation, and the fact has "yes" → the answer is
  yes / no = (fact yes) XOR (negated);
- otherwise the fact has "text" → the answer is that text (case and surrounding spaces ignored);
- otherwise the fact has "pick" → the answer is that list of patterns;
- otherwise → the answer is "the key itself".

## Combining DeepSeek's majority `ds` with Haiku's reading `hk` on a critical question
- ds asks → the result is ds (asks);
- Haiku failed (hk has "error": true) → the result asks;
- hk asks → the result asks;
- the two readings lead to the same answer → the result is ds (does not ask), even when their keys or shapes differ;
- otherwise → the result asks.
Examples: ds spons_future (yes true) and hk authorized negated (yes true → negated false … see facts) compare by their
yes / no; ds gpa (text "3.5") and hk gpa_current (text "N/A") differ → ask; ds email and hk secondary_email (text equal) → same.
