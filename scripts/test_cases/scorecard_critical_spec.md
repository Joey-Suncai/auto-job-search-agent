# Platform scorecard — wrong-answer bars (decided 2026-11-05)

Each wrong answer found after a submit names its application folder and its question; it is CRITICAL or NON-CRITICAL
(its `class` when given; otherwise a question about work authorization / visa / sponsorship, education, his contact
details, EEO, or his experience / references is critical, anything else non-critical).

For each platform, over its SUBMITTED applications:
1. Critical bar: the platform passes only when it has 0 critical wrong answers.
2. Non-critical bar: accuracy = 1 − (non-critical wrong answers ÷ non-critical answers on those submitted forms). The
   platform passes when accuracy ≥ 0.95. When the number of non-critical answers is unknown (0), it passes only when there
   is no non-critical wrong answer at all.
3. The wrong-answer bar (`wrong_ok`) passes only when BOTH bars pass.
4. Re-certification entry {since, need} for a platform: the critical bar is passed instead when at least `need` applications
   were submitted at or after `since` and none of them has a CRITICAL wrong answer (earlier critical wrong answers are
   forgiven; non-critical ones never count for re-certification). The non-critical bar is unchanged.
5. Wrong answers on applications that were never submitted, or of another platform, do not count.
