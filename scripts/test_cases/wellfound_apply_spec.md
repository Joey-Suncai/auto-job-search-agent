# wellfound_apply.py — spec (JSA-171)

A Wellfound job page (`https://wellfound.com/jobs/<id>-<slug>`) is read in a browser and turned into a **page record**:
`{"url": final page URL, "title": page title, "text": visible page text, "links": [{"href": absolute URL, "text": label}],
"buttons": [button labels], "data_urls": [{"key": JSON key, "url": URL}]}` and, only after a "peek" click on the Apply
button, also `"opened": [URLs that the click opened]`, `"modal": text of a dialog that appeared` (may be ""), `"peeked": true`.
Every key may be missing (= empty). The functions below decide where the job is really applied to.

**Known ATS hosts** (a host equal to, or a subdomain of, one of these): workable.com · applytojob.com, jazzhr.com ·
adp.com · ultipro.com, ukg.net · rippling.com, rippling-ats.com · dayforcehcm.com · paycomonline.net, paycom.com ·
taleo.net · paylocity.com · eightfold.ai · avature.net · yello.co · jobvite.com · clearcompany.com · breezy.hr ·
jibeapply.com · bamboohr.com · smartrecruiters.com · icims.com · oraclecloud.com · successfactors.com,
successfactors.eu, sapsf.com · greenhouse.io · myworkdayjobs.com, myworkdaysite.com · ashbyhq.com · lever.co.
(Also a SuccessFactors site on a company's own host: query `ats=successf…`, or a path exactly `/job/<slug>/<8–12 digits>`.)
**Wellfound hosts**: wellfound.com, angel.co, angellist.com and their subdomains.
**Never-apply hosts**: linkedin.com, twitter.com, x.com, facebook.com, instagram.com, youtube.com, github.com,
crunchbase.com, glassdoor.com, medium.com, apple.com, google.com, goo.gl, bit.ly and their subdomains.

## clean_url(url) → str
- HTML entities are decoded and the value trimmed; JSON escapes `\/`, `/`, `&` become `/`, `/`, `&`.
- Not an http(s) URL (empty, None, `mailto:`, `javascript:`, a relative path) → "".
- **Redirect wrappers are unwrapped**: when the URL's host is NOT a known ATS host and one of its query parameters named
  `url`, `u`, `q`, `target`, `redirect`, `redirect_url`, `redirecturl`, `dest`, `destination`, `to`, `link`, `goto`, `out`
  (name case-insensitive) holds an absolute http(s) URL (percent-encoded once or twice is fine), that inner URL replaces
  it; repeated up to 3 times. A known ATS URL is never unwrapped, even if it has such a parameter.
- **Tracking parameters are dropped** (name case-insensitive): `utm_*`, `gh_src`, `source`, `src`, `ref`, `referrer`,
  `ref_src`, `fbclid`, `gclid`, `msclkid`, `mc_cid`, `mc_eid`, `iisn`, `iis`, `trk`, `lever-source`, `lever-via`, `_hs…`.
  Every other parameter is kept in its order (e.g. `gh_jid`, `jobId`, `for`, `token`), written exactly as it was (no
  re-encoding). When none is left there is no `?`.
- Path and fragment are kept as they are; the scheme is lower-cased.

## posting_like(url) → bool
True when the URL names one posting rather than a board or careers home page:
- Workday host: only when the path contains `/job/` or `/details/` (nothing else counts for Workday).
- Greenhouse host: path has `/jobs/<digits>` or a query `gh_jid=<digits>`.
- Workable host: path has `/j/<6 or more letters/digits>`.
- Any URL (including the above when their own rule did not hold, except Workday): a UUID
  (8-4-4-4-12 hex) in the path or in a query value, or 5 or more digits in a row in the path or in a query value.
- Otherwise False (e.g. `https://jobs.lever.co/acme`, `https://acme.com/careers`, `https://boards.greenhouse.io/acme`).

## pick_external(page) → str
The best external apply URL, cleaned with clean_url, or "".
Candidates, in this source order:
 (a) each URL in `opened`;
 (b) each link whose `text` contains the word "apply" (any case; "Apply", "Apply now", "Apply on company site") —
     first the links in `modal_links` (the peeked dialog's links, `[{"href", "text"}]`, read and never clicked), then
     the page's `links`;
 (c) each data_url whose `key` contains "apply", "application", "external" or "ats" (any case);
 (d) any other link href or data_url url that, cleaned, is on a known ATS host AND is posting_like.
A candidate is dropped when its cleaned URL is "", is on a Wellfound host or a never-apply host, or repeats an earlier one.
Best = known ATS and posting_like, then known ATS (not posting_like), then posting_like (not ATS), then the rest;
ties → earlier source, then earlier position. A plain company-website link (label "acme.com", no "apply") is not a
candidate unless rule (d) takes it.

## classify(page) → {"via", "ats_url", "apply_url", "reason"}
`via` is one of blocked | signin | closed | external | wellfound | unknown; `ats_url` and `apply_url` are "" unless
stated; `reason` is a short human sentence (not tested exactly — the cases test via, ats_url, apply_url only).
Checked in this order; the first that holds wins:
1. **blocked**: the title contains a challenge phrase — "verify you are human", "are you a robot", "just a moment",
   "security check", "captcha", "access denied", "unusual activity", "unusual traffic", "press and hold",
   "press & hold" (any case) — or the text does and the text is shorter than 1500 characters; or `click_out_stop` is
   "blocked".
2. **signin**: `click_out_stop` is "signin"; or `url` is on a Wellfound host and its path starts with `/login`, `/signin`,
   `/sign_in`, `/signup`, `/sign_up`, `/join` or `/onboarding`; or a URL in `opened` is such a Wellfound sign-in URL.
3. **closed**: `url` is on a Wellfound host and its path has no `/jobs/<digits>` (the job page redirected elsewhere, e.g.
   to `/jobs` or `/company/acme`); or the title or text says the job is gone — "no longer accepting applications",
   "(job|position|posting|listing) [is] no longer (available|active|open)", "this (job|position|posting|listing|role)
   (has been|is|was) (closed|filled|removed|archived)", "position has been filled", "(job|posting|listing) has expired",
   "job not found", "page not found" (any case). An empty `url` skips the URL checks of 2 and 3.
4. **external**: pick_external(page) is not "" → apply_url = that URL; ats_url = the same URL when it is posting_like,
   else "" (a board / careers page).
4a. **external** (no URL): `modal` says "managed outside of Wellfound" / "managed outside Wellfound", or "apply on
   website" / "apply on the website" / "apply on company website" / "apply on the company website" / "apply on the
   company's website" (any case) → apply_url = ats_url = "" (live 11-05: the dialog's "Apply on website" is a button
   without a link; clicking it changes the job's status in the candidate's Wellfound account, so it is clicked only with
   `--click-out` — then the URL it opened is in `opened` and step 4 already took it).
4b. **wellfound**: `modal` says "cannot apply to this job because your profile is missing" (any case); the reason lists
   the lines after that sentence up to "please apply again" (live 11-05: "Skills", "Work Experience").
5. **wellfound**: `modal` contains "send application", "submit application", "write a note", "note to", "cover letter",
   "apply to", "your application" or "why are you" / "why do you" (any case).
6. **signin**: the text says "log in to apply", "login to apply", "sign in to apply", "signin to apply", "sign up to
   apply", "create an account to apply" or "join wellfound to apply" (any case).
7. **wellfound**: a button label or link text starts with "Applied", "Already applied" or "You applied" (any case) — not counting a link whose
   path is `/jobs/applications` (the site's own "Applied" navigation tab, on every page when signed in; live run 11-05).
8. **wellfound**: a link on a Wellfound host whose text is exactly an apply label.
9. **unknown**: a button whose label is exactly an apply label (reason says a peek is needed, or — when `peeked` is
   true — that the peek opened nothing readable).
10. **unknown**: otherwise (no Apply control).
An **apply label** (whole label, any case, surrounding spaces ignored): "Apply", "Apply now", "Easy apply",
"Easy apply now", "Apply on company site", "Apply on the company website", "Apply on employer site",
"Apply at company site", "Apply via company website", "Apply externally". "Send application" or "Submit" is not one.

## Click-out (`--click-out`, method B, live 11-05)
With `--click-out`, a peeked dialog that matches 4a has its "Apply on website" control clicked; the URL the click
opened (new tab or navigation, after redirects) is appended to `opened`, and when that page was a challenge or a sign-in
page the record gets `click_out_stop` = "blocked" / "signin" (classify steps 1 / 2). Two pure helpers decide this:

### click_out_index(labels) → int or None
`labels` = the visible control labels inside the dialog, in order (strings; may be empty or missing → None). Returns
the index of the first label that is, as a whole (any case, surrounding spaces ignored), one of "Apply on website",
"Apply on the website", "Apply on company website", "Apply on the company website", "Apply on company's website",
"Apply on the company's website". Anything else never counts — "Apply", "Apply now", "Send application", "Submit",
"Cancel", "Apply on website now", "Click here to apply on website", a label that only contains the phrase. None when no
label matches.

### opened_stop(info) → str
`info` = what the click opened: {"url", "title", "text", "password": true when a visible password field is on the page}
(any key may be missing; None = {}). Returns, first that holds:
- "blocked": the title contains a challenge phrase (the list in classify step 1), or the text does and the text is
  shorter than 1500 characters;
- "signin": the url is on a Wellfound host with a sign-in path (classify step 2's list), or `password` is true (on any
  host — a company sign-in page);
- "" otherwise (an ordinary company job page: its URL is only recorded).

## page_from_html(html, url) → dict
A saved page's HTML → {"url": url as given, "title", "text", "links", "buttons", "data_urls"}:
- title = the `<title>` text, entities decoded, whitespace collapsed, trimmed ("" if none).
- links = every `<a href=…>` (in page order) whose href, joined with `url` when relative (when `url` is "" the href is
  used as is), is http(s); text = the anchor's visible text (tags removed, entities decoded, whitespace collapsed), or
  its `aria-label` when that text is empty. Anchors without href, or `mailto:` / `javascript:` / `#` links, are left out.
  Anchors inside `<script>` / `<style>` do not count.
- buttons = the visible text of every `<button>` (same cleaning), empty ones left out, in page order.
- data_urls = from the content of every `<script>`: each JSON pair `"<key>": "http…"` whose key ends in `url`, `Url`,
  `URL`, `link`, `Link`, `href` or `Href` → {"key", "url"} in order, with `\/` and `/` → `/`, `&` → `&`.
- text = the visible text (scripts and styles removed); each block (p / div / h1–h6 / li / section / main / button /
  a / br) on its own line; not tested beyond "contains" checks.
