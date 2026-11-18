# Spec: choose_verify_link — which Gmail mail verifies the Workday account the agent just created (JSA-274)

After the agent creates a Workday candidate account, the tenant sends a verification mail with a link. The agent reads
the recent mails of Joey's inbox and must pick the link that verifies THIS tenant's account — never another tenant's,
never a marketing mail, never an old mail. Senders vary: many tenants send from `*@myworkday.com` or
`otp.workday.com`, but some send from their own HR domain (Vanguard: `CrewCentral_noreply@vanguardhr.com`, subject
"Verify your candidate account", link `https://vanguard.wd5.myworkdayjobs.com/vanguard_external/activate/<token>`).

Inputs: `mails` = list of {date (ISO 8601 with zone), from (display name + address), subject, body (text/HTML, links
as plain https URLs)}; `since` = when the account form was submitted (ISO 8601 with zone); `page_url` = the Workday
page the agent is on; `company` = the company name (may be empty).

Tenant: `https://vanguard.wd5.myworkdayjobs.com/...` → tenant host `vanguard.wd5.myworkdayjobs.com`, tenant name
`vanguard`. `https://wd3.myworkdaysite.com/recruiting/brevanhoward/...` → tenant host `wd3.myworkdaysite.com` with
path `/recruiting/brevanhoward/`, tenant name `brevanhoward`.

Rules:
1. Only mails dated at or after `since` minus 2 minutes count (clock margin). Older mails are ignored entirely.
2. A verification link is an https URL whose text contains `verify`, `activat` or `confirm`.
3. A **tenant link** is a verification link on this tenant: on the tenant host (for myworkdaysite.com: also under
   `/recruiting/<tenant name>/`), or on any `*.myworkday.com` host with `/<tenant name>/` in its path.
4. A mail is accepted when any one of these holds: (a) its subject reads as an account-verification request
   ("Verify your candidate account", "Verify your email", "Please verify your e-mail address", "Activate your account",
   "Confirm your email address", and similar); (b) its body has a tenant link; (c) the sender's e-mail domain contains
   the tenant name or the company name (letters and digits only, case-insensitive; e.g. `vanguardhr.com` contains
   `vanguard`).
5. The link returned from an accepted mail: its tenant link, if it has one. A mail without a tenant link gives a link
   only if BOTH (a) and (c) hold — then its first verification link on a Workday host (`myworkdayjobs.com`,
   `myworkdaysite.com`, `myworkday.com`) or on the sender's own domain. Otherwise the mail gives nothing (another
   tenant's verify mail, a marketing mail).
6. If several mails give a link: prefer a tenant link over any other link; among equals prefer a mail whose subject reads
   as a verification request; then the newest.
7. Nothing found → null.
