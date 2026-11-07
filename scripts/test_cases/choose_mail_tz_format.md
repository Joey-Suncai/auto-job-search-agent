Each case: {"name": "...", "mails": [{"sent": "2026-11-02T19:30:00 or with -06:00", "from": "...", "subject": "..."}],
 "since": "...", "company": "...", "expect": "<subject>" or null}
Most cases mix zone-less and zoned times; include cases where a zone-less time is just before / just after `since` once read as UTC.
