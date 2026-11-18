Each case is a JSON object:
{"name": "<short unique id>", "since": "<ISO 8601 with zone>", "page_url": "<Workday page URL>", "company": "<name or empty>",
 "mails": [{"date": "<ISO 8601 with zone>", "from": "<Display Name <addr@domain>>", "subject": "...", "body": "..."}],
 "expect": "<the exact URL that must be returned, or null>", "rule": "<quoted spec sentence>", "ambiguous": false}
Bodies are short and contain the URLs as plain text. Use realistic tenants (e.g. vanguard.wd5.myworkdayjobs.com,
invesco.wd1.myworkdayjobs.com, wd3.myworkdaysite.com/recruiting/brevanhoward). Cover: verify mails from odd sender
domains, marketing / job-alert mails, another tenant's verify mail, an old verify mail before `since`, the clock margin,
several matching mails (preference order), a mail with only a non-Workday link.
