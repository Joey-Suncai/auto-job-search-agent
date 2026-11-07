A JSON array of 20 cases: {"name": "<unique snake_case>", "page": "<a small HTML document>", "expect": {"title": "...", "text": "...", "loc": "..."} or null}.
Keep each page short (a <title>, a header block with Job Location / Visa Sponsorship lines, "About the job", a few JD
paragraphs or list items, then optionally "Apply Now" and "About the company" with more lines). Cover: no About-the-job
block, no About-the-company block, entities, script/style blocks containing the marker words, nested tags, missing
<title>, titles with " at " inside the job title (e.g. "Data at Scale Intern at Acme • NYC | Wellfound"), Job Location
missing, empty JD.
