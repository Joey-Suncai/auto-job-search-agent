# Spec: refit_chance (JSA-102) — refit the chance-of-an-interview weights from tracker outcomes

Factors: every job has four chance factors in 0..1: s_referral, s_timing, s_sponsor, s_fresh (in this order).
Current prior weights: s_referral 0.40, s_timing 0.25, s_sponsor 0.20, s_fresh 0.15.

## outcome(status)
- Case-insensitive, surrounding spaces ignored.
- "Assessment", "Interview", "Offer" → 1 (positive reply).
- "Rejected", "Applied", "No response" → 0.
- Anything else ("Shortlisted", "Applied (unconfirmed)", "Withdrawn", "", missing) → None (not a usable application).

## build_sample(apps, jobs, today, min_days)
- apps: list of tracker rows {status, applied_on "YYYY-MM-DD", job_id, company}. jobs: dict id → job row.
- A row is used only when: outcome(status) is not None; applied_on parses as a date; (today − applied_on) in days
  ≥ min_days (exactly min_days days old IS included); job_id is a key of jobs.
- Each used row → {"x": [s_referral, s_timing, s_sponsor, s_fresh] as floats, "y": outcome}.
- Rows not used are counted in `excluded` by reason; the order of checks is: status, applied_on, age, job lookup
  (a row is counted once, under the first failing check). Reason strings: "not submitted / unknown status",
  "no applied_on", "applied < {min_days} days ago", "job not in jobs.jsonl".
- Returns (rows, excluded) where excluded is a dict reason → count.

## normalise(beta)  (beta = the 4 factor coefficients)
- Negative coefficients count as 0; the result is the positive parts divided by their sum, so it sums to 1.
- If no coefficient is positive, every factor gets 1/4.

## fit_map(rows, mu, sd)
- Logistic regression P(y=1) = sigmoid(b0 + Σ βk xk) with independent normal priors N(mu_i, sd_i²) on [b0, β1..β4];
  returns the posterior mode (MAP) and the covariance (inverse Hessian at the mode).
- With no rows the result equals mu exactly, and the covariance diagonal equals sd².
- Properties: a very small sd (e.g. 1e-4) on a coefficient pins it at its mu (within 1e-3). If positives have a higher
  value of a factor than negatives (everything else equal) and that factor's prior is mu=0 with a wide sd, its fitted
  coefficient is > 0; if positives have a lower value, < 0. Adding more data never increases any posterior variance
  above the prior variance (diagonal of covariance ≤ sd² for each coefficient). Results are finite even when the data
  are perfectly separable (the prior keeps them finite).

## spearman(a, b)
- Spearman rank correlation with average ranks for ties. Identical order → 1; reversed order → −1.
- Fewer than 2 items → 1. If either list is constant → 1 (defined as "no change").

## ranking_change(jobs, w_old, w_new, top=50)
- Only jobs with elig == "可投" count; n = their number.
- score = value(v_level) + 30 × chance, chance = Σ w[k] × job[k]; value: top 70, standard 40, exclude 0,
  off_target 0 (missing v_level = standard).
- Returns spearman of old vs new scores, top_overlap = size of the intersection of the top-`top` ids by old score and by
  new score, b_c_flips = number of "standard" jobs whose (chance ≥ 0.5) differs between old and new weights,
  c_to_b = flips from < 0.5 to ≥ 0.5, b_to_c = the rest of the flips.
- Same weights old and new → spearman 1, top_overlap = min(top, n), b_c_flips 0.

## needed_n(rows, beta, prior_sd, target=0.5)
- For each factor: None when the factor has the same value in every row (no variation, the data can never inform it);
  otherwise a positive integer (more variation → a smaller or equal number).
