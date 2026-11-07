# fit_bt: value weights from pairwise choices (Bradley-Terry with a normal prior)

Input: pairs, each with two cards a and b; a card has `role` (ai_pm, data_analysis, pm, ai_nonengineering, ai_engineering,
data, other), `sponsor` (offers, strong, some, unknown) and `green_card` (true/false); answers {q: "A" | "B"}.
Features: one weight per role except the baseline "data" (and "other", which gets none); one per sponsor level except the
baseline "unknown"; one for green_card. A card's value = sum of the weights of its features (baseline levels = 0).
P(choose a over b) = sigmoid(value(a) − value(b)). Weights are the maximum a posteriori estimate under an independent
normal prior N(0, prior_sd²) per weight (default prior_sd = 2).

1. A pair marked `repeat_of: q0` is not used for fitting; it is reported in `consistency` with `same` = true when the job
   chosen (by id) is the same as in pair q0.
2. Pairs whose answer is missing or not "A"/"B" are ignored.
3. With no usable choices, every weight is 0.
4. If a feature level is always chosen whenever it differs (and nothing else differs), its weight is positive; always
   rejected → negative. Swapping A/B in a pair together with its answer gives the same weights.
5. Weights are finite even when the choices are perfectly separable (the prior keeps them bounded); a smaller prior_sd
   gives weights closer to 0.
6. `fit_agreement` = "k/n": n = fitted choices, k = how many the fitted weights predict (value of chosen > other).
   `against_model` lists the q of the fitted choices it does not predict.

7. Model "v1" (the default since 2026-11-03): role weights (baseline data) plus one continuous feature h1b_log10 =
   log10(1 + h1b_fy25) of the card (a missing count = 0). Its weight is positive when the larger company is always
   chosen with roles equal, negative when always rejected.
8. Several rounds can be merged: round r's question numbers get +100·r (a repeat_of moves with them), answers follow.
9. Leave-one-out: for each fitted choice, refit without it and predict it; reports predicted "k/n" and the mean
   log-loss −log P(observed choice). With all choices identical in direction and features, every left-out choice is
   predicted (k = n).
