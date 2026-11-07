# Which mail is the company's application receipt — mails with and without a time zone

choose_mail(mails, since, company) returns the subject of the newest mail sent at or after `since` whose subject reads as
an application receipt ("Thank you for applying…", "Thank you for your application…", "Thanks for your interest…",
"Application received") and whose sender or subject names the company; otherwise null.
Times are ISO 8601. A time WITHOUT a time zone (e.g. "2026-11-02T19:30:00") is read as UTC. A time with a zone is
compared with its zone ("2026-11-02T13:30:00-06:00" is the same moment as "2026-11-02T19:30:00"). This applies to the
mails' sent times and to `since`. Mixing mails with and without a zone must never fail.
