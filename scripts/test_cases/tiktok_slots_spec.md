# TikTok / ByteDance application slots (JSA-097)

Source: TikTok Early Careers FAQ (https://lifeattiktok.com/earlycareers/faq, read 2026-11-02): "There are two application
periods each year, and you may apply for up to two Early Career positions per program within each application period.
Application periods: January to June · July to December. The application limit applies to both TikTok and its
affiliates' jobs globally. This application limit does not apply to PhD and Project Intern opportunities." Submitted
applications cannot be withdrawn. Referral applications count too.

## Definitions
- **Limited company**: a job or tracker row whose company name contains "tiktok", "bytedance", "capcut" or "lemon8"
  (any case, e.g. "TikTok USDS Joint Venture" counts), OR whose url / ats_url is on lifeattiktok.com, careers.tiktok.com,
  jobs.bytedance.com or joinbytedance.com. TikTok and ByteDance share ONE limit.
- **Exempt role**: the title contains "Project Intern" or "PhD" / "Ph.D." (any case). Exempt roles never use a slot and
  are never refused.
- **Period** of a date YYYY-MM-DD: months 01–06 → "<YYYY>H1"; months 07–12 → "<YYYY>H2". 2026-07-01 … 2026-12-31 =
  "2026H2"; 2027-01-01 … 2027-06-30 = "2027H1". The period of an application is the period of the day it was SUBMITTED
  (applied_on), not the internship's season.
- **Program**: "intern" when level or title contains the word "intern" / "internship" (any case; "International" is not it); "graduate" when level contains "new grad",
  "full-time", "full time" or "graduate"; otherwise "unknown". Each program has its own 2 slots per period.
- **Counted tracker row**: a limited-company row, not exempt, whose status is anything other than "Shortlisted" or empty
  (Applied, Applied (unconfirmed), Assessment, Interview, Rejected, Offer… all count — a rejected application was still
  submitted). Its period = the row's `period` field when present, else the period of `applied_on`, else of `updated`.
- **Limit**: 2 per (period, program).

## check(job, apps, today) → result
- `limited` = the job is a limited company; `counted` = limited and not exempt.
- `period` = the period of `today` (the day the application would be submitted); `program` = the job's program.
- `used` = number of counted tracker rows in that period whose program equals the job's program. When the job's
  program is "unknown", `used` = the larger of the intern count and the graduate count (plus rows of unknown program
  are added to every program's count). Rows with the same job_id as the job are still counted (re-applying is no
  free slot).
- `remaining` = max(0, 2 − used).
- `allowed` = true when the job is not counted (not limited, or exempt); otherwise true only when remaining > 0.
- `reason`: empty when allowed; otherwise a sentence that names the period, the program and "2/2" (or "<used>/2").
- Rows in other periods never count. Shortlisted rows never count.
