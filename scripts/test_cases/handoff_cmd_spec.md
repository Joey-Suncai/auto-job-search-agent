# When does the runner open a Lever application in Joey's own browser?

handoff_cmd(ats, status, problems, url, browser) returns the macOS command ["open", "-a", browser, url], or null.
It returns the command only when ALL of these hold:
- ats is exactly "lever";
- status is exactly "unconfirmed" (Submit was clicked, every check passed, but no confirmation page or e-mail);
- problems is an empty list (any problem → null);
- browser is a non-empty string (e.g. "Microsoft Edge");
- url is a Lever apply page: https://jobs.lever.co/<site>/<36-character posting id of hex digits and dashes>/apply
  (also https://jobs.eu.lever.co/…; an optional trailing "/" is allowed; matching is case-insensitive). Not http://,
  not a posting page without "/apply", not "/apply/thanks", not other hosts, no query string.
Every other input returns null (statuses "submitted", "blocked", "dry-run"; ats "ashby", "greenhouse", "workday").
