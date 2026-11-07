# posting_key(url) — which tabs belong to one posting (JSA-145)
After a confirmed submit every other job-Chrome tab of the same posting is closed. posting_key(url) returns:
- Lever (`jobs.lever.co` or `jobs.eu.lever.co`): "<site>/<uuid>" — the site slug and the 36-character posting id, whatever follows (/apply, /thanks, /already-received?ms=…).
- Ashby (`jobs.ashbyhq.com`): "<org>/<uuid>" likewise (/application, /form …).
- Greenhouse: the number in a `token=` or `gh_jid=` query parameter.
- Anything else: the URL without its query string and fragment.
- Oracle Recruiting Cloud (`<host>.oraclecloud.com/hcmUI/CandidateExperience/<lang>/sites/<site>/job/<id>` or
  `…/requisitions/preview/<id>`): "<host in lower case>/job/<id>" — the same for every page of that job's apply flow
  (/apply/email, /apply/section/3, ?query). Added JSA-147.
