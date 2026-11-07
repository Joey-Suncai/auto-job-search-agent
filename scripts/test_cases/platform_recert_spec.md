# Platform scorecard — re-certification after wrong answers

The scorecard certifies a platform only when, among other bars, it has **0 wrong answers** (a wrong answer = a line in the
wrong-answers log naming a submitted application folder of that platform).

Re-certification (decided 2026-11-05): a platform may have an entry {since: <time>, need: <n>}. For such a platform the
wrong-answer bar is passed when BOTH hold:
1. at least `need` applications of that platform were SUBMITTED at or after `since` (the time of the submit), and
2. none of those applications submitted at or after `since` has a wrong answer.
Wrong answers on applications submitted BEFORE `since` no longer fail the bar (they still appear in the platform's total
wrong-answer count). An application submitted before `since` does not count toward `need`. An application that was never
submitted counts toward nothing.
A platform WITHOUT an entry keeps the plain rule: any wrong answer fails the bar.
An entry for one platform never changes another platform.
