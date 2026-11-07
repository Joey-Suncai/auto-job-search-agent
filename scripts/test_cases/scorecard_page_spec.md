# Platform scorecard: proof of receipt by e-mail or by the confirmation page (Joey 2026-11-04)

A submitted application has proof of receipt when EITHER
(a) the company's e-mail for that job (type Confirmation, Rejection, Assessment, Interview or Offer) is dated on the submit day or up to 2 days after, OR
(b) page proof: page_proof(line, shot) is true for the first "submitted" line of that folder.

## page_proof(line, shot) -> bool
line = one results line: {status, by?, confirmed_by?}. shot = whether the folder holds a submitted_confirmation screenshot.
- If line.by is "joey" → false (Joey's own submits never count by the page).
- If line.confirmed_by is exactly "email" → false.
- If line.confirmed_by is a string starting with "page" (e.g. "page", "page (my-profile: Applied on 11/04)") → true, whether or not there is a screenshot.
- If confirmed_by is missing or empty → true only when shot is true.
- Any other confirmed_by value → false.

## Counting
For each platform: confirmed = submits with proof (a) or (b); an application with e-mail proof counts as e-mail (by_email),
otherwise one with page proof counts as page (by_page); never both. A submit with neither proof is pending when today is on
or before submit day + 2, otherwise it is missing. confirm_rate = confirmed / (submitted − pending).
