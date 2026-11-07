# Is a Lever application folder owned by the runner right now?

The local fill server serves a browser extension that is installed both in Joey's own browser and in the automated
"job Chrome". While the automated runner works on an application folder it keeps a mark file in that folder
({"ts": <unix seconds when the run started>, "pid": <process id>, "at": "...", "phase": "...", "url": "..."}) and deletes
it right after writing its own result. While the runner owns the folder, the server must neither fill the page for the
extension nor record a confirmation page as "submitted by Joey".

runner_owns(mark, now_ts, alive) → true / false
- mark = the parsed mark file, or null when there is none (or it could not be parsed). Anything that is not an object → false.
- ts must be a number (int or float; a boolean is not a number; a string such as "1700000000" is not a number) → otherwise false.
- age = now_ts − ts. age greater than 7200 seconds (2 hours) → false (stale). age exactly 7200 → still owned (if the
  process lives). A ts in the future by more than 60 seconds (age < −60) → false; up to 60 s in the future is accepted
  (clock skew).
- pid must be present and truthy (0, null, "" or missing → false). Then alive(pid) decides: the result is true only if
  alive(pid) is truthy. alive is never called when an earlier rule already returned false.
- The other keys (at, phase, url) never matter.
