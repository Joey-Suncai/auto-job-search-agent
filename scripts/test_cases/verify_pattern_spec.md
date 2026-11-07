# Which Workday verification link belongs to this application

Several Workday applications run at the same time, each on its own company "tenant", and each may send an account
verification e-mail. Given the URL of the application page (page_url) and a link found in an e-mail, decide whether the
link is this tenant's verification link (true) or not (false).
- A tenant on *.myworkdayjobs.com is identified by the full host name, e.g. invesco.wd1.myworkdayjobs.com. The link must
  start with https:// + exactly that host + "/", and contain "verify", "activat" or "confirm" somewhere after it.
  Another company's host (vsp.wd1.myworkdayjobs.com), or the same company on another data center (invesco.wd5…), is false.
- A tenant on wd3.myworkdaysite.com (shared host) is identified by host + "/recruiting/<tenant>"; the link must start with
  https://wd3.myworkdaysite.com/recruiting/<tenant>/ (same tenant name, case-insensitive) and contain verify/activat/confirm.
- Host comparison is case-insensitive. A link without verify/activat/confirm (e.g. a job posting link) is false.
- When page_url is empty or not a Workday URL, any https link on a myworkday/workday host that contains verify/activat/confirm is true.
